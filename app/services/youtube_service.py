"""
YouTube Service for extracting and processing video transcripts
"""
import re
import os
import tempfile
from typing import List, Dict, Optional
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from pytubefix import Channel, YouTube
from app import db
from app.models.youtube_channel import YouTubeChannel
from app.models.youtube_video import YouTubeVideo
from app.models.topic import Topic
from app.services.rag_service import RAGService
from app.ai_engines.factory import AIEngineFactory
import openai


class YouTubeService:
    """Service for processing YouTube channels and videos"""

    @staticmethod
    def extract_channel_id_from_url(channel_url: str) -> Optional[str]:
        """Extract channel ID or handle from YouTube URL"""
        # Patterns:
        # https://www.youtube.com/@channelhandle
        # https://www.youtube.com/channel/UCXXXXXXX
        # https://www.youtube.com/c/channelname

        patterns = [
            r'youtube\.com/@([^/\?]+)',
            r'youtube\.com/channel/([^/\?]+)',
            r'youtube\.com/c/([^/\?]+)',
            r'youtube\.com/user/([^/\?]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, channel_url)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def normalize_channel_url(channel_url: str) -> str:
        """
        Normalize channel URL - pytubefix 10.x supports @username URLs directly

        Args:
            channel_url: Original channel URL

        Returns:
            Normalized channel URL (returns as-is since pytubefix handles all formats)
        """
        # pytubefix 10.x supports all URL formats (@username, channel/ID, /c/, /user/)
        # No normalization needed, return as-is
        return channel_url

    @staticmethod
    def extract_channel_info(channel_url: str) -> Dict[str, any]:
        """
        Extract channel metadata using pytubefix

        Returns:
            dict with: channel_id, channel_name, description, video_count
        """
        try:
            # Normalize URL to channel/ID format (more reliable than @username)
            normalized_url = YouTubeService.normalize_channel_url(channel_url)

            channel = Channel(normalized_url)

            # Extract channel ID from URL if possible
            channel_id = YouTubeService.extract_channel_id_from_url(normalized_url)
            if not channel_id:
                channel_id = channel.channel_id if hasattr(channel, 'channel_id') else 'unknown'

            return {
                'channel_id': channel_id,
                'channel_name': channel.channel_name,
                'description': getattr(channel, 'description', ''),
                'channel_url': normalized_url,
            }
        except Exception as e:
            raise Exception(f"Error al extraer información del canal: {str(e)}")

    @staticmethod
    def get_channel_videos(channel_url: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get list of videos from a YouTube channel (optimized version)

        Args:
            channel_url: URL of the YouTube channel
            limit: Maximum number of videos to retrieve (None = all videos)

        Returns:
            List of dicts with video information
        """
        try:
            # Normalize URL to channel/ID format
            normalized_url = YouTubeService.normalize_channel_url(channel_url)

            print(f"[YouTubeService] Obteniendo lista de videos del canal (optimizado)...")
            channel = Channel(normalized_url)
            videos = []

            # Get video objects (pytubefix 10.x returns YouTube objects, not URLs)
            # This is fast - just gets the video IDs
            video_objects = list(channel.videos)
            print(f"[YouTubeService] Encontrados {len(video_objects)} videos en el canal")

            # Apply limit if specified
            if limit:
                video_objects = video_objects[:limit]

            # Extract metadata for each video - OPTIMIZED to skip unavailable videos fast
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def get_video_info(yt):
                try:
                    video_id = yt.video_id
                    video_url = f'https://www.youtube.com/watch?v={video_id}'

                    # Try to get basic info - if video is unavailable, this will fail fast
                    title = yt.title  # This triggers metadata fetch

                    return {
                        'video_id': video_id,
                        'title': title,
                        'url': video_url,
                        'duration': getattr(yt, 'length', 0),
                        'published_at': getattr(yt, 'publish_date', None),
                    }
                except Exception as e:
                    # Skip unavailable videos silently
                    return None

            # Process videos in parallel for speed (max 10 threads)
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(get_video_info, yt): yt for yt in video_objects}

                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        videos.append(result)

            print(f"[YouTubeService] Cargados {len(videos)} videos válidos de {len(video_objects)} totales")
            return videos

        except Exception as e:
            raise Exception(f"Error al obtener videos del canal: {str(e)}")

    @staticmethod
    def generate_transcript_with_whisper(video_url: str, use_groq: bool = None) -> Optional[List[Dict]]:
        """
        Generate transcript using Whisper API (Groq or OpenAI)

        Args:
            video_url: YouTube video URL
            use_groq: If True, use Groq. If False, use OpenAI. If None, auto-detect based on available keys.

        Returns:
            List of dicts with 'text', 'start', 'duration' keys, or None if failed
        """
        temp_audio_path = None
        try:
            # Auto-detect provider if not specified
            if use_groq is None:
                groq_key = os.environ.get('GROQ_API_KEY')
                openai_key = os.environ.get('OPENAI_API_KEY')

                if groq_key:
                    use_groq = True
                elif openai_key:
                    use_groq = False
                else:
                    print("[YouTubeService] ERROR: No hay API key configurada (GROQ_API_KEY o OPENAI_API_KEY)")
                    return None

            api_provider = "Groq" if use_groq else "OpenAI"
            print(f"[YouTubeService] Generando transcripción con Whisper ({api_provider}) para {video_url}")

            # Download audio
            yt = YouTube(video_url)
            # Use lower bitrate for faster transcription
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').asc().first()

            if not audio_stream:
                print(f"[YouTubeService] No se encontró stream de audio")
                return None

            # Get file extension from stream
            file_extension = audio_stream.subtype

            # Ensure compatible format for Whisper
            if file_extension not in ['m4a', 'mp3', 'webm', 'mp4', 'mpga', 'wav', 'mpeg', 'ogg', 'flac']:
                file_extension = 'mp4'  # Default to mp4

            # Download to temporary file
            temp_dir = tempfile.gettempdir()
            temp_filename = f'yt_audio_{video_url.split("=")[-1]}'

            print(f"[YouTubeService] Descargando audio ({audio_stream.mime_type}, {audio_stream.abr})...")
            downloaded_path = audio_stream.download(output_path=temp_dir, filename=temp_filename)

            # Rename to have correct extension
            temp_audio_path = os.path.join(temp_dir, f'{temp_filename}.{file_extension}')
            if downloaded_path != temp_audio_path:
                os.rename(downloaded_path, temp_audio_path)

            # Check file size (25MB limit for Whisper API)
            file_size = os.path.getsize(temp_audio_path) / (1024 * 1024)  # MB
            if file_size > 25:
                print(f"[YouTubeService] ⚠️  Archivo muy grande ({file_size:.1f} MB), comprimiendo...")
                # TODO: Implement compression or chunking for large files
                print(f"[YouTubeService] ERROR: Archivo excede 25MB - compresión no implementada aún")
                return None

            print(f"[YouTubeService] Transcribiendo con Whisper ({api_provider}, {file_size:.1f} MB)...")

            # Transcribe with Whisper
            if use_groq:
                # Use Groq (faster and free/cheaper)
                from groq import Groq
                groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'))
                with open(temp_audio_path, 'rb') as audio_file:
                    response = groq_client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=audio_file,
                        response_format="verbose_json",
                        language="es"
                    )
            else:
                # Use OpenAI
                with open(temp_audio_path, 'rb') as audio_file:
                    client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
                    response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",
                        language="es"
                    )

            # Convert Whisper response to transcript format
            transcript = []
            if hasattr(response, 'segments') and response.segments:
                for segment in response.segments:
                    # Access segment attributes (not dict keys)
                    transcript.append({
                        'text': getattr(segment, 'text', '').strip(),
                        'start': getattr(segment, 'start', 0.0),
                        'duration': getattr(segment, 'end', 0.0) - getattr(segment, 'start', 0.0)
                    })
            else:
                # Fallback: single segment
                transcript.append({
                    'text': response.text,
                    'start': 0.0,
                    'duration': yt.length
                })

            print(f"[YouTubeService] ✅ Transcripción generada: {len(transcript)} segmentos")
            return transcript

        except Exception as e:
            print(f"[YouTubeService] Error al generar transcripción con Whisper: {str(e)}")
            return None
        finally:
            # Clean up temporary file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

    @staticmethod
    def extract_video_transcript(video_id: str, language: str = 'es', generate_if_missing: bool = True) -> Optional[List[Dict]]:
        """
        Extract transcript from a YouTube video. If not available, generate with Whisper.

        Args:
            video_id: YouTube video ID
            language: Preferred language (default: 'es' for Spanish)
            generate_if_missing: If True, generate transcript with Whisper if not available

        Returns:
            List of dicts with 'text', 'start', 'duration' keys, or None if not available
        """
        try:
            # Try direct approach first - simpler and more reliable
            try:
                # Try to get transcript in Spanish or English
                return YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en', 'es-ES', 'en-US'])
            except:
                pass

            # Fallback: use transcript list API
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            try:
                # Try manual transcript first
                transcript = transcript_list.find_transcript([language, 'en'])
                return transcript.fetch()
            except:
                pass

            try:
                # Fallback to auto-generated
                transcript = transcript_list.find_generated_transcript([language, 'en'])
                return transcript.fetch()
            except:
                pass

            # Last resort: get any available transcript
            for transcript in transcript_list:
                try:
                    return transcript.fetch()
                except:
                    continue

            # If no transcript found and generation is enabled, use Whisper
            if generate_if_missing:
                video_url = f'https://www.youtube.com/watch?v={video_id}'
                return YouTubeService.generate_transcript_with_whisper(video_url)

            return None

        except (TranscriptsDisabled, NoTranscriptFound):
            print(f"[YouTubeService] No hay transcripción disponible para video {video_id}")

            # Try to generate with Whisper
            if generate_if_missing:
                video_url = f'https://www.youtube.com/watch?v={video_id}'
                return YouTubeService.generate_transcript_with_whisper(video_url)

            return None
        except Exception as e:
            print(f"[YouTubeService] Error al extraer transcripción de {video_id}: {str(e)}")
            return None

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Convert seconds to MM:SS or HH:MM:SS format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def chunk_transcript(transcript_data: List[Dict], chunk_size: int = 3000,
                        chunk_overlap: int = 200) -> List[Dict]:
        """
        Split transcript into chunks for embedding

        Args:
            transcript_data: List of transcript segments
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks in characters

        Returns:
            List of dicts with 'text', 'timestamp', 'chunk_index'
        """
        if not transcript_data:
            return []

        # Combine all text
        full_text = ' '.join([segment['text'] for segment in transcript_data])

        chunks = []
        chunk_index = 0
        start_idx = 0

        while start_idx < len(full_text):
            # Get chunk
            end_idx = start_idx + chunk_size
            chunk_text = full_text[start_idx:end_idx]

            # Try to break at sentence boundary
            if end_idx < len(full_text):
                last_period = chunk_text.rfind('.')
                last_question = chunk_text.rfind('?')
                last_exclamation = chunk_text.rfind('!')
                break_point = max(last_period, last_question, last_exclamation)

                if break_point > chunk_size - 200:  # Only if reasonably close to end
                    chunk_text = chunk_text[:break_point + 1]
                    end_idx = start_idx + break_point + 1

            # Find corresponding timestamp (approximate)
            char_position_ratio = start_idx / len(full_text)
            estimated_seconds = char_position_ratio * transcript_data[-1]['start']
            timestamp = YouTubeService.format_timestamp(estimated_seconds)

            chunks.append({
                'text': chunk_text.strip(),
                'timestamp': timestamp,
                'chunk_index': chunk_index
            })

            chunk_index += 1
            start_idx = end_idx - chunk_overlap

        return chunks

    @staticmethod
    def process_youtube_channel(channel_id: int, video_limit: Optional[int] = None) -> Dict:
        """
        Process a YouTube channel: extract videos, transcripts, and create embeddings

        Args:
            channel_id: Database ID of the YouTubeChannel
            video_limit: Maximum number of videos to process

        Returns:
            Dict with processing statistics
        """
        channel = YouTubeChannel.query.get(channel_id)
        if not channel:
            raise Exception("Canal no encontrado")

        print(f"[YouTubeService] Procesando canal: {channel.channel_name}")

        # Get videos from channel
        videos_data = YouTubeService.get_channel_videos(channel.channel_url, limit=video_limit)

        videos_processed = 0
        videos_skipped = 0
        topics_created = 0

        rag_service = RAGService()
        ai_engine = AIEngineFactory.create()

        for video_data in videos_data:
            video_id = video_data['video_id']

            # Check if video already exists
            existing_video = YouTubeVideo.query.filter_by(video_id=video_id).first()
            if existing_video:
                print(f"[YouTubeService] Video {video_id} ya existe, omitiendo...")
                continue

            # Extract transcript
            transcript = YouTubeService.extract_video_transcript(video_id)

            if not transcript:
                # Create video record but mark as no transcript
                video = YouTubeVideo(
                    channel_id=channel.id,
                    video_id=video_id,
                    title=video_data['title'],
                    url=video_data['url'],
                    duration=video_data['duration'],
                    published_at=video_data['published_at'],
                    transcript_available=False
                )
                db.session.add(video)
                videos_skipped += 1
                print(f"[YouTubeService] Video {video_id} sin transcripción, omitido")
                continue

            # Create video record
            video = YouTubeVideo(
                channel_id=channel.id,
                video_id=video_id,
                title=video_data['title'],
                url=video_data['url'],
                duration=video_data['duration'],
                published_at=video_data['published_at'],
                transcript_available=True
            )
            db.session.add(video)
            db.session.flush()  # Get video.id

            # Chunk transcript
            chunks = YouTubeService.chunk_transcript(transcript)

            # Store in RAG
            rag_service.store_video_chunks(channel.id, video_id, chunks)

            # Create topic automatically (1 video = 1 topic)
            topic_description = chunks[0]['text'][:200] if chunks else ''
            topic = Topic(
                source_type='youtube_video',
                video_id=video.id,
                topic_name=video.title,
                description=topic_description,
                order=videos_processed
            )
            db.session.add(topic)

            videos_processed += 1
            topics_created += 1

            print(f"[YouTubeService] Video procesado: {video.title}")

        # Update channel status
        channel.video_count = videos_processed + videos_skipped
        channel.processed = True
        db.session.commit()

        return {
            'videos_processed': videos_processed,
            'videos_skipped': videos_skipped,
            'topics_created': topics_created
        }

    @staticmethod
    def process_selected_videos(channel_id: int, selected_video_ids: List[str]) -> Dict:
        """
        Process only selected videos from a YouTube channel

        Args:
            channel_id: Database ID of the YouTubeChannel
            selected_video_ids: List of YouTube video IDs to process

        Returns:
            Dict with processing statistics
        """
        channel = YouTubeChannel.query.get(channel_id)
        if not channel:
            raise Exception("Canal no encontrado")

        print(f"[YouTubeService] Procesando {len(selected_video_ids)} videos seleccionados del canal: {channel.channel_name}")

        # Get all videos from channel to find the selected ones
        all_videos = YouTubeService.get_channel_videos(channel.channel_url)

        # Filter only selected videos
        videos_data = [v for v in all_videos if v['video_id'] in selected_video_ids]

        if not videos_data:
            raise Exception("No se encontraron los videos seleccionados en el canal")

        videos_processed = 0
        videos_skipped = 0
        topics_created = 0

        rag_service = RAGService()

        for video_data in videos_data:
            video_id = video_data['video_id']

            # Check if video already exists
            existing_video = YouTubeVideo.query.filter_by(video_id=video_id).first()
            if existing_video:
                print(f"[YouTubeService] Video {video_id} ya existe, omitiendo...")
                videos_skipped += 1
                continue

            # Extract transcript
            transcript = YouTubeService.extract_video_transcript(video_id)

            if not transcript:
                # Create video record but mark as no transcript
                video = YouTubeVideo(
                    channel_id=channel.id,
                    video_id=video_id,
                    title=video_data['title'],
                    url=video_data['url'],
                    duration=video_data['duration'],
                    published_at=video_data['published_at'],
                    transcript_available=False
                )
                db.session.add(video)
                videos_skipped += 1
                print(f"[YouTubeService] Video {video_id} sin transcripción, omitido")
                continue

            # Create video record
            video = YouTubeVideo(
                channel_id=channel.id,
                video_id=video_id,
                title=video_data['title'],
                url=video_data['url'],
                duration=video_data['duration'],
                published_at=video_data['published_at'],
                transcript_available=True
            )
            db.session.add(video)
            db.session.flush()  # Get video.id

            # Chunk transcript
            chunks = YouTubeService.chunk_transcript(transcript)

            # Store in RAG
            rag_service.store_video_chunks(channel.id, video_id, chunks)

            # Create topic automatically (1 video = 1 topic)
            topic_description = chunks[0]['text'][:200] if chunks else ''
            topic = Topic(
                source_type='youtube_video',
                video_id=video.id,
                topic_name=video.title,
                description=topic_description,
                order=videos_processed
            )
            db.session.add(topic)

            videos_processed += 1
            topics_created += 1

            print(f"[YouTubeService] Video procesado: {video.title}")

        # Update channel status
        channel.video_count = videos_processed + videos_skipped
        channel.processed = True
        db.session.commit()

        return {
            'videos_processed': videos_processed,
            'videos_skipped': videos_skipped,
            'topics_created': topics_created
        }
