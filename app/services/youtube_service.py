"""
YouTube Service for extracting and processing video transcripts
"""
import re
import os
import json
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
        Get list of videos from a YouTube channel.

        Uses yt-dlp (flat extraction) as the primary method because it is far more
        reliable than pytubefix for channel enumeration, with pytubefix as fallback.

        Args:
            channel_url: URL of the YouTube channel
            limit: Maximum number of videos to retrieve (None = all videos)

        Returns:
            List of dicts with video information
        """
        try:
            normalized_url = YouTubeService.normalize_channel_url(channel_url)

            # Primary: yt-dlp flat listing (fast + reliable)
            videos = YouTubeService._get_channel_videos_ytdlp(normalized_url, limit)
            if videos:
                return videos

            # Fallback: pytubefix (kept for resilience)
            print("[YouTubeService] yt-dlp no devolvió videos, intentando pytubefix...")
            return YouTubeService._get_channel_videos_pytubefix(normalized_url, limit)

        except Exception as e:
            raise Exception(f"Error al obtener videos del canal: {str(e)}")

    @staticmethod
    def _get_channel_videos_ytdlp(channel_url: str, limit: Optional[int] = None) -> List[Dict]:
        """List channel videos using yt-dlp flat extraction."""
        try:
            import yt_dlp

            # Point to the channel's "videos" tab for a clean video listing
            list_url = channel_url.rstrip('/')
            if not list_url.endswith('/videos'):
                list_url += '/videos'

            ydl_opts = {
                **YouTubeService._get_ytdlp_base_opts(),
                'extract_flat': 'in_playlist',  # don't resolve each video (fast)
                'skip_download': True,
            }
            if limit:
                ydl_opts['playlistend'] = limit

            print(f"[YouTubeService] Listando videos del canal con yt-dlp: {list_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(list_url, download=False)

            # Flatten entries (a channel may return nested tabs/playlists)
            def iter_entries(node):
                for entry in (node.get('entries') or []):
                    if not entry:
                        continue
                    if entry.get('entries'):
                        yield from iter_entries(entry)
                    else:
                        yield entry

            videos = []
            for e in iter_entries(info or {}):
                vid = e.get('id')
                if not vid:
                    continue
                try:
                    duration = int(e.get('duration') or 0)
                except (TypeError, ValueError):
                    duration = 0
                videos.append({
                    'video_id': vid,
                    'title': e.get('title') or f'Video {vid}',
                    'url': e.get('url') or f'https://www.youtube.com/watch?v={vid}',
                    'duration': duration,
                    'published_at': None,  # not available in flat mode
                })
                if limit and len(videos) >= limit:
                    break

            print(f"[YouTubeService] yt-dlp: {len(videos)} videos encontrados en el canal")
            return videos

        except Exception as e:
            print(f"[YouTubeService] yt-dlp falló al listar el canal: {type(e).__name__}: {e}")
            return []

    @staticmethod
    def _get_channel_videos_pytubefix(channel_url: str, limit: Optional[int] = None) -> List[Dict]:
        """Fallback channel listing using pytubefix."""
        print(f"[YouTubeService] Obteniendo lista de videos del canal (pytubefix)...")
        channel = Channel(channel_url)
        video_objects = list(channel.videos)
        if limit:
            video_objects = video_objects[:limit]

        videos = []
        for yt in video_objects:
            try:
                video_id = yt.video_id
            except Exception:
                continue
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            try:
                title = yt.title
            except Exception:
                title = None
            videos.append({
                'video_id': video_id,
                'title': title or f'Video {video_id}',
                'url': video_url,
                'duration': getattr(yt, 'length', 0) or 0,
                'published_at': getattr(yt, 'publish_date', None),
            })

        print(f"[YouTubeService] pytubefix: {len(videos)} videos válidos")
        return videos

    @staticmethod
    def _download_audio(video_url: str) -> Optional[str]:
        """
        Download audio from a YouTube video to a temporary file.
        Uses yt-dlp primarily (more robust + cookie support), with pytubefix as fallback.

        Args:
            video_url: YouTube video URL

        Returns:
            Path to the downloaded audio file, or None if failed
        """
        # 1. Try yt-dlp first (most robust against bot detection)
        result = YouTubeService._download_audio_with_ytdlp(video_url)
        if result:
            return result

        # 2. Fallback: pytubefix
        print("[YouTubeService] yt-dlp falló, intentando con pytubefix...")
        return YouTubeService._download_audio_with_pytubefix(video_url)

    @staticmethod
    def _download_audio_with_ytdlp(video_url: str) -> Optional[str]:
        """Download audio using yt-dlp (supports cookies and better bot bypass)."""
        try:
            import yt_dlp

            video_id = video_url.split("=")[-1]
            temp_dir = tempfile.gettempdir()
            outtmpl = os.path.join(temp_dir, f'yt_audio_{video_id}.%(ext)s')

            ydl_opts = {
                **YouTubeService._get_ytdlp_base_opts(),
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '64',
                }],
                'noplaylist': True,
            }

            print(f"[YouTubeService] Descargando audio con yt-dlp...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # After postprocessing, file will be .mp3
            final_path = os.path.join(temp_dir, f'yt_audio_{video_id}.mp3')
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path) / (1024 * 1024)
                print(f"[YouTubeService] Audio descargado (yt-dlp): {file_size:.1f} MB")
                return final_path

            # Look for any extension (fallback if ffmpeg conversion failed)
            import glob
            candidates = glob.glob(os.path.join(temp_dir, f'yt_audio_{video_id}.*'))
            if candidates:
                path = candidates[0]
                file_size = os.path.getsize(path) / (1024 * 1024)
                print(f"[YouTubeService] Audio descargado (yt-dlp, sin conversión): {file_size:.1f} MB")
                return path

            return None

        except Exception as e:
            print(f"[YouTubeService] Error descargando audio con yt-dlp: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _download_audio_with_pytubefix(video_url: str) -> Optional[str]:
        """Download audio using pytubefix (fallback)."""
        try:
            yt = YouTube(video_url)
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').asc().first()

            if not audio_stream:
                print(f"[YouTubeService] No se encontró stream de audio")
                return None

            file_extension = audio_stream.subtype
            if file_extension not in ['m4a', 'mp3', 'webm', 'mp4', 'mpga', 'wav', 'mpeg', 'ogg', 'flac']:
                file_extension = 'mp4'

            temp_dir = tempfile.gettempdir()
            temp_filename = f'yt_audio_{video_url.split("=")[-1]}'

            print(f"[YouTubeService] Descargando audio con pytubefix ({audio_stream.mime_type}, {audio_stream.abr})...")
            downloaded_path = audio_stream.download(output_path=temp_dir, filename=temp_filename)

            temp_audio_path = os.path.join(temp_dir, f'{temp_filename}.{file_extension}')
            if downloaded_path != temp_audio_path:
                os.rename(downloaded_path, temp_audio_path)

            file_size = os.path.getsize(temp_audio_path) / (1024 * 1024)
            print(f"[YouTubeService] Audio descargado (pytubefix): {file_size:.1f} MB")
            return temp_audio_path

        except Exception as e:
            print(f"[YouTubeService] Error descargando audio con pytubefix: {str(e)}")
            return None

    @staticmethod
    def _detect_whisper_provider() -> str:
        """
        Detect which Whisper provider to use based on available API keys and libraries.

        Returns:
            'groq', 'openai', 'local', or 'none'
        """
        if os.environ.get('GROQ_API_KEY'):
            return 'groq'
        if os.environ.get('OPENAI_API_KEY'):
            return 'openai'
        try:
            import faster_whisper
            return 'local'
        except ImportError:
            pass
        return 'none'

    @staticmethod
    def _transcribe_with_groq(audio_path: str) -> Optional[List[Dict]]:
        """Transcribe audio using Groq Whisper API."""
        from groq import Groq
        groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

        file_size = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size > 25:
            print(f"[YouTubeService] ERROR: Archivo excede 25MB ({file_size:.1f} MB) para Groq API")
            return None

        with open(audio_path, 'rb') as audio_file:
            response = groq_client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="verbose_json",
                language="es"
            )

        return YouTubeService._parse_api_response(response)

    @staticmethod
    def _transcribe_with_openai(audio_path: str) -> Optional[List[Dict]]:
        """Transcribe audio using OpenAI Whisper API."""
        file_size = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size > 25:
            print(f"[YouTubeService] ERROR: Archivo excede 25MB ({file_size:.1f} MB) para OpenAI API")
            return None

        with open(audio_path, 'rb') as audio_file:
            client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                language="es"
            )

        return YouTubeService._parse_api_response(response)

    @staticmethod
    def _transcribe_with_faster_whisper(audio_path: str) -> Optional[List[Dict]]:
        """
        Transcribe audio locally using faster-whisper.
        No file size limit, no API key required.
        Uses 'medium' model by default (good balance of speed/quality for Spanish).
        """
        try:
            from faster_whisper import WhisperModel

            model_size = os.environ.get('WHISPER_LOCAL_MODEL', 'medium')
            device = os.environ.get('WHISPER_DEVICE', 'auto')
            compute_type = os.environ.get('WHISPER_COMPUTE_TYPE', 'auto')

            print(f"[YouTubeService] Cargando modelo faster-whisper ({model_size}, device={device})...")
            model = WhisperModel(model_size, device=device, compute_type=compute_type)

            print(f"[YouTubeService] Transcribiendo localmente...")
            segments, info = model.transcribe(audio_path, language="es", beam_size=5)

            transcript = []
            for segment in segments:
                transcript.append({
                    'text': segment.text.strip(),
                    'start': segment.start,
                    'duration': segment.end - segment.start
                })

            print(f"[YouTubeService] Transcripción local completada: {len(transcript)} segmentos "
                  f"(idioma detectado: {info.language}, probabilidad: {info.language_probability:.2f})")
            return transcript if transcript else None

        except Exception as e:
            print(f"[YouTubeService] Error en transcripción local con faster-whisper: {str(e)}")
            return None

    @staticmethod
    def _parse_api_response(response) -> List[Dict]:
        """Parse Whisper API response (Groq/OpenAI) into transcript format."""
        transcript = []
        if hasattr(response, 'segments') and response.segments:
            for segment in response.segments:
                transcript.append({
                    'text': getattr(segment, 'text', '').strip(),
                    'start': getattr(segment, 'start', 0.0),
                    'duration': getattr(segment, 'end', 0.0) - getattr(segment, 'start', 0.0)
                })
        else:
            transcript.append({
                'text': response.text,
                'start': 0.0,
                'duration': 0.0
            })
        return transcript

    @staticmethod
    def generate_transcript_with_whisper(video_url: str, use_groq: bool = None) -> Optional[List[Dict]]:
        """
        Generate transcript using Whisper. Auto-detects the best available provider:
        1. Groq API (if GROQ_API_KEY is set) - fastest
        2. OpenAI API (if OPENAI_API_KEY is set)
        3. faster-whisper local (if installed) - no API key needed, no file size limit

        Args:
            video_url: YouTube video URL
            use_groq: If True, force Groq. If False, force OpenAI. If None, auto-detect.

        Returns:
            List of dicts with 'text', 'start', 'duration' keys, or None if failed
        """
        temp_audio_path = None
        try:
            # Determine provider
            if use_groq is True:
                provider = 'groq'
            elif use_groq is False:
                provider = 'openai'
            else:
                provider = YouTubeService._detect_whisper_provider()

            if provider == 'none':
                print("[YouTubeService] ERROR: No hay proveedor de transcripción disponible. "
                      "Configure GROQ_API_KEY, OPENAI_API_KEY, o instale faster-whisper.")
                return None

            provider_names = {'groq': 'Groq API', 'openai': 'OpenAI API', 'local': 'faster-whisper (local)'}
            print(f"[YouTubeService] Generando transcripción con {provider_names[provider]} para {video_url}")

            # Download audio
            temp_audio_path = YouTubeService._download_audio(video_url)
            if not temp_audio_path:
                return None

            file_size = os.path.getsize(temp_audio_path) / (1024 * 1024)
            print(f"[YouTubeService] Transcribiendo con {provider_names[provider]} ({file_size:.1f} MB)...")

            # Transcribe with selected provider, with fallback to local
            transcript = None

            if provider == 'groq':
                transcript = YouTubeService._transcribe_with_groq(temp_audio_path)
                if not transcript and file_size > 25:
                    print("[YouTubeService] Archivo excede 25MB, intentando transcripción local...")
                    transcript = YouTubeService._transcribe_with_faster_whisper(temp_audio_path)
            elif provider == 'openai':
                transcript = YouTubeService._transcribe_with_openai(temp_audio_path)
                if not transcript and file_size > 25:
                    print("[YouTubeService] Archivo excede 25MB, intentando transcripción local...")
                    transcript = YouTubeService._transcribe_with_faster_whisper(temp_audio_path)
            elif provider == 'local':
                transcript = YouTubeService._transcribe_with_faster_whisper(temp_audio_path)

            if transcript:
                print(f"[YouTubeService] Transcripción generada: {len(transcript)} segmentos")
            return transcript

        except Exception as e:
            print(f"[YouTubeService] Error al generar transcripción con Whisper: {str(e)}")
            return None
        finally:
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

    _cookies_writable_path = None

    @staticmethod
    def _get_writable_cookies_path() -> Optional[str]:
        """
        Returns a writable copy of the cookies file. yt-dlp needs to write to the
        cookies file to update session tokens, so a read-only mount won't work.
        We copy it once to /tmp and reuse it.
        """
        cookies_file = os.environ.get('YOUTUBE_COOKIES_FILE')
        if not cookies_file or not os.path.exists(cookies_file):
            return None

        # Use a stable path in /tmp so yt-dlp can update it across requests
        writable_path = os.path.join(tempfile.gettempdir(), 'yt_cookies.txt')

        # Copy if missing or if source is newer (e.g., admin updated cookies.txt)
        try:
            src_mtime = os.path.getmtime(cookies_file)
            needs_copy = (
                not os.path.exists(writable_path)
                or os.path.getmtime(writable_path) < src_mtime
            )
            if needs_copy:
                import shutil
                shutil.copy2(cookies_file, writable_path)
                os.chmod(writable_path, 0o644)
                print(f"[YouTubeService] Cookies copiadas a {writable_path} (escribible)")
        except Exception as e:
            print(f"[YouTubeService] Error copiando cookies: {e}")
            return None

        return writable_path

    @staticmethod
    def _get_ytdlp_base_opts() -> Dict:
        """
        Base yt-dlp options with anti-bot bypasses:
        - Realistic user agent
        - Cookies file (if YOUTUBE_COOKIES_FILE is set) - copied to a writable location
        - Cookies from browser (if YOUTUBE_COOKIES_FROM_BROWSER is set, e.g. 'firefox', 'chrome')
        """
        opts = {
            'quiet': True,
            'no_warnings': True,
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            # Required for yt-dlp 2026+: download EJS challenge solver from GitHub.
            # Combined with deno (JS runtime) and bgutil-pot (PO Token), this allows
            # yt-dlp to bypass YouTube's bot detection on datacenter IPs.
            'remote_components': ['ejs:github'],
        }

        # When using cookies, only use the 'web' player client (cookies are web-only).
        # When using bgutil-pot without cookies, 'tv' or 'mweb' work best.
        disable_cookies = os.environ.get('YOUTUBE_DISABLE_COOKIES', '').lower() in ('1', 'true', 'yes')
        cookies_present = not disable_cookies and (
            os.environ.get('YOUTUBE_COOKIES_FILE')
            or os.environ.get('YOUTUBE_COOKIES_FROM_BROWSER')
        )
        if cookies_present:
            opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
        else:
            # Without cookies + bgutil-pot: tv and mweb clients work best with PO tokens
            opts['extractor_args'] = {'youtube': {'player_client': ['tv', 'mweb', 'web']}}

        # Allow disabling cookies via env var. When using bgutil-pot (PO Token provider),
        # cookies can actually hurt: yt-dlp requires data_sync_id for authenticated GVS
        # PO Tokens, which is awkward to extract. bgutil-pot alone (anonymous mode)
        # often works better.
        disable_cookies = os.environ.get('YOUTUBE_DISABLE_COOKIES', '').lower() in ('1', 'true', 'yes')

        if not disable_cookies:
            cookies_path = YouTubeService._get_writable_cookies_path()
            if cookies_path:
                opts['cookiefile'] = cookies_path
                print(f"[YouTubeService] Usando cookies desde archivo: {cookies_path}")

            cookies_browser = os.environ.get('YOUTUBE_COOKIES_FROM_BROWSER')
            if cookies_browser:
                opts['cookiesfrombrowser'] = (cookies_browser,)
                print(f"[YouTubeService] Usando cookies del navegador: {cookies_browser}")
        else:
            print("[YouTubeService] Cookies deshabilitadas (YOUTUBE_DISABLE_COOKIES=1), usando solo bgutil-pot")

        return opts

    @staticmethod
    def _extract_transcript_with_ytdlp(video_id: str, languages=('es', 'es-ES', 'en', 'en-US')) -> Optional[List[Dict]]:
        """
        Extract subtitles using yt-dlp (more robust against bot-detection).
        Returns list of segments with 'text', 'start', 'duration' or None.
        """
        try:
            import yt_dlp
            import tempfile
            import glob

            url = f'https://www.youtube.com/watch?v={video_id}'
            with tempfile.TemporaryDirectory() as tmpdir:
                outtmpl = os.path.join(tmpdir, '%(id)s.%(ext)s')
                ydl_opts = {
                    **YouTubeService._get_ytdlp_base_opts(),
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': list(languages),
                    'subtitlesformat': 'json3',
                    'outtmpl': outtmpl,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Look for any downloaded .json3 subtitle file
                sub_files = sorted(glob.glob(os.path.join(tmpdir, f'{video_id}*.json3')))
                if not sub_files:
                    return None

                # Prefer manual subs over auto; prefer preferred language order
                def score(path):
                    name = os.path.basename(path)
                    for i, lang in enumerate(languages):
                        if f'.{lang}.' in name:
                            return i
                    return len(languages)
                sub_files.sort(key=score)

                with open(sub_files[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)

                segments = []
                for event in data.get('events', []):
                    if 'segs' not in event:
                        continue
                    text = ''.join(seg.get('utf8', '') for seg in event['segs']).strip()
                    if not text:
                        continue
                    segments.append({
                        'text': text,
                        'start': (event.get('tStartMs', 0) or 0) / 1000.0,
                        'duration': (event.get('dDurationMs', 0) or 0) / 1000.0,
                    })
                return segments if segments else None
        except Exception as e:
            print(f"[YouTubeService] yt-dlp subtitles failed for {video_id}: {type(e).__name__}: {e}")
            return None

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
        # 1. Try yt-dlp first - most robust against bot detection
        try:
            result = YouTubeService._extract_transcript_with_ytdlp(video_id)
            if result:
                print(f"[YouTubeService] Transcripción obtenida vía yt-dlp para {video_id} ({len(result)} segmentos)")
                return result
        except Exception as e:
            print(f"[YouTubeService] yt-dlp falló para {video_id}: {type(e).__name__}: {e}")

        # 2. Try youtube-transcript-api direct approach
        try:
            result = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'en', 'es-ES', 'en-US'])
            if result:
                print(f"[YouTubeService] Transcripción obtenida vía youtube-transcript-api para {video_id}")
                return result
        except Exception as e:
            print(f"[YouTubeService] youtube-transcript-api directo falló para {video_id}: {type(e).__name__}")

        # 3. Try transcript list API (manual, auto-generated, any)
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual transcript first
            try:
                transcript = transcript_list.find_transcript([language, 'en'])
                result = transcript.fetch()
                if result:
                    return result
            except Exception:
                pass

            # Fallback to auto-generated
            try:
                transcript = transcript_list.find_generated_transcript([language, 'en'])
                result = transcript.fetch()
                if result:
                    return result
            except Exception:
                pass

            # Last resort: any available transcript
            for transcript in transcript_list:
                try:
                    result = transcript.fetch()
                    if result:
                        return result
                except Exception:
                    continue
        except Exception as e:
            print(f"[YouTubeService] list_transcripts falló para {video_id}: {type(e).__name__}")

        # 4. Final fallback: generate transcript with Whisper (Groq/OpenAI/local)
        if generate_if_missing:
            print(f"[YouTubeService] No se encontró transcripción existente para {video_id}, intentando generar con Whisper...")
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            return YouTubeService.generate_transcript_with_whisper(video_url)

        print(f"[YouTubeService] No hay transcripción disponible para video {video_id}")
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
