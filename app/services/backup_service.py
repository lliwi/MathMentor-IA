"""
Backup Service - Handles database and file backups
"""
import os
import subprocess
import tarfile
import shutil
from datetime import datetime
from pathlib import Path


class BackupService:
    """Service for creating and managing backups"""
    
    BACKUP_DIR = '/app/backups'
    UPLOADS_DIR = '/app/uploads'
    
    @staticmethod
    def ensure_backup_directory():
        """Ensure backup directory exists"""
        Path(BackupService.BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def create_backup():
        """
        Create a complete backup including:
        - PostgreSQL database (with pgvector embeddings)
        - Uploaded PDF files
        
        Returns:
            dict: Backup information (filename, size, timestamp)
        """
        BackupService.ensure_backup_directory()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'mathmentor_backup_{timestamp}'
        backup_path = os.path.join(BackupService.BACKUP_DIR, backup_name)
        
        # Create temporary directory for backup files
        temp_dir = f'{backup_path}_temp'
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 1. Backup PostgreSQL database
            db_backup_file = os.path.join(temp_dir, 'database.sql')
            db_host = os.getenv('DB_HOST', 'db')
            db_name = os.getenv('DB_NAME', 'mathmentor')
            db_user = os.getenv('DB_USER', 'mathmentor_user')
            db_password = os.getenv('DB_PASSWORD', 'mathmentor_password')
            
            # Use pg_dump to backup database (includes all tables and pgvector data)
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            subprocess.run([
                'pg_dump',
                '-h', db_host,
                '-U', db_user,
                '-d', db_name,
                '-f', db_backup_file,
                '--no-owner',
                '--no-acl'
            ], env=env, check=True)
            
            # 2. Copy uploaded files
            uploads_backup_dir = os.path.join(temp_dir, 'uploads')
            if os.path.exists(BackupService.UPLOADS_DIR):
                shutil.copytree(BackupService.UPLOADS_DIR, uploads_backup_dir)
            
            # 3. Create metadata file
            metadata_file = os.path.join(temp_dir, 'backup_info.txt')
            with open(metadata_file, 'w') as f:
                f.write(f'Backup Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                f.write(f'Database: {db_name}\n')
                f.write(f'MathMentor IA - Complete Backup\n')
                f.write(f'Includes: Database (with RAG embeddings) + PDF files\n')
            
            # 4. Create compressed archive
            archive_file = f'{backup_path}.tar.gz'
            with tarfile.open(archive_file, 'w:gz') as tar:
                tar.add(temp_dir, arcname=backup_name)
            
            # Get file size
            file_size = os.path.getsize(archive_file)
            
            # Clean up temp directory
            shutil.rmtree(temp_dir)
            
            return {
                'filename': f'{backup_name}.tar.gz',
                'path': archive_file,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'timestamp': timestamp,
                'created_at': datetime.now()
            }
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise Exception(f'Error creating backup: {str(e)}')
    
    @staticmethod
    def list_backups():
        """
        List all available backups
        
        Returns:
            list: List of backup information dictionaries
        """
        BackupService.ensure_backup_directory()
        
        backups = []
        
        for filename in os.listdir(BackupService.BACKUP_DIR):
            if filename.endswith('.tar.gz'):
                filepath = os.path.join(BackupService.BACKUP_DIR, filename)
                file_size = os.path.getsize(filepath)
                file_mtime = os.path.getmtime(filepath)
                
                # Extract timestamp from filename
                try:
                    timestamp_str = filename.replace('mathmentor_backup_', '').replace('.tar.gz', '')
                    created_at = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                except:
                    created_at = datetime.fromtimestamp(file_mtime)
                
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'created_at': created_at
                })
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
    
    @staticmethod
    def delete_backup(filename):
        """
        Delete a specific backup file
        
        Args:
            filename (str): Name of the backup file to delete
            
        Returns:
            bool: True if deleted successfully
        """
        filepath = os.path.join(BackupService.BACKUP_DIR, filename)
        
        if os.path.exists(filepath) and filename.endswith('.tar.gz'):
            os.remove(filepath)
            return True
        
        return False
    
    @staticmethod
    def get_backup_path(filename):
        """
        Get full path to a backup file
        
        Args:
            filename (str): Name of the backup file
            
        Returns:
            str: Full path to backup file or None if not found
        """
        filepath = os.path.join(BackupService.BACKUP_DIR, filename)
        
        if os.path.exists(filepath) and filename.endswith('.tar.gz'):
            return filepath
        
        return None
    
    @staticmethod
    def restore_backup(filename):
        """
        Restore from a backup file
        
        Args:
            filename (str): Name of the backup file to restore
            
        Returns:
            dict: Restoration status and information
        """
        filepath = BackupService.get_backup_path(filename)
        
        if not filepath:
            raise Exception('Backup file not found')
        
        # Create temporary directory for extraction
        temp_dir = os.path.join(BackupService.BACKUP_DIR, 'restore_temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Extract archive
            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            # Find the extracted directory
            extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
            if not extracted_dirs:
                raise Exception('Invalid backup archive')
            
            extracted_dir = os.path.join(temp_dir, extracted_dirs[0])
            
            # Restore database
            db_backup_file = os.path.join(extracted_dir, 'database.sql')
            if os.path.exists(db_backup_file):
                db_host = os.getenv('DB_HOST', 'db')
                db_name = os.getenv('DB_NAME', 'mathmentor')
                db_user = os.getenv('DB_USER', 'mathmentor_user')
                db_password = os.getenv('DB_PASSWORD', 'mathmentor_password')
                
                env = os.environ.copy()
                env['PGPASSWORD'] = db_password
                
                # Terminate all connections to the database first
                subprocess.run([
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', 'postgres',
                    '-c', f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}' AND pid <> pg_backend_pid();"
                ], env=env, check=True)

                # Drop and recreate database (careful!)
                subprocess.run([
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', 'postgres',
                    '-c', f'DROP DATABASE IF EXISTS {db_name}'
                ], env=env, check=True)

                subprocess.run([
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', 'postgres',
                    '-c', f'CREATE DATABASE {db_name}'
                ], env=env, check=True)

                # Recreate pgvector extension
                subprocess.run([
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', db_name,
                    '-c', 'CREATE EXTENSION IF NOT EXISTS vector;'
                ], env=env, check=True)
                
                # Restore database
                subprocess.run([
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', db_name,
                    '-f', db_backup_file
                ], env=env, check=True)
            
            # Restore uploaded files
            uploads_backup_dir = os.path.join(extracted_dir, 'uploads')
            if os.path.exists(uploads_backup_dir):
                # Clean existing uploads directory content (don't remove the directory itself, it might be a Docker volume)
                if os.path.exists(BackupService.UPLOADS_DIR):
                    for item in os.listdir(BackupService.UPLOADS_DIR):
                        item_path = os.path.join(BackupService.UPLOADS_DIR, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                else:
                    os.makedirs(BackupService.UPLOADS_DIR, exist_ok=True)

                # Copy backup uploads content
                for item in os.listdir(uploads_backup_dir):
                    src = os.path.join(uploads_backup_dir, item)
                    dst = os.path.join(BackupService.UPLOADS_DIR, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            
            # Clean up temp directory
            shutil.rmtree(temp_dir)
            
            return {
                'success': True,
                'message': 'Backup restored successfully',
                'restored_at': datetime.now()
            }
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise Exception(f'Error restoring backup: {str(e)}')
    @staticmethod
    def upload_backup(file_storage):
        """
        Upload a backup file to the server
        
        Args:
            file_storage: FileStorage object from Flask request.files
            
        Returns:
            dict: Upload status and information
        """
        BackupService.ensure_backup_directory()
        
        # Validate filename
        filename = file_storage.filename
        if not filename or not filename.endswith('.tar.gz'):
            raise Exception('El archivo debe ser un backup válido (.tar.gz)')
        
        # Validate it's a MathMentor backup
        if not filename.startswith('mathmentor_backup_'):
            raise Exception('El archivo no parece ser un backup de MathMentor IA')
        
        # Check if file already exists
        filepath = os.path.join(BackupService.BACKUP_DIR, filename)
        if os.path.exists(filepath):
            raise Exception('Ya existe un backup con ese nombre')
        
        # Save file
        file_storage.save(filepath)
        
        # Validate it's a valid tar.gz file
        try:
            with tarfile.open(filepath, 'r:gz') as tar:
                # Check if it contains expected files
                members = tar.getmembers()
                has_database = any('database.sql' in m.name for m in members)
                
                if not has_database:
                    os.remove(filepath)
                    raise Exception('El backup no contiene un archivo de base de datos válido')
        except tarfile.TarError:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise Exception('El archivo no es un archivo tar.gz válido')
        
        # Get file info
        file_size = os.path.getsize(filepath)
        
        return {
            'filename': filename,
            'path': filepath,
            'size': file_size,
            'size_mb': round(file_size / (1024 * 1024), 2),
            'uploaded_at': datetime.now()
        }
