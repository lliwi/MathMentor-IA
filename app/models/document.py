"""
Document model - gestor documental compartido para admins y profesores
"""
from datetime import datetime
from app import db


class Document(db.Model):
    """Archivo (PDF, imagen, etc.) subido por el personal como material de apoyo"""
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)   # extensión: pdf, png, docx...
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)       # bytes
    category = db.Column(db.String(50), nullable=True)     # etiqueta opcional
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_by = db.relationship('User', backref='documents', foreign_keys=[uploaded_by_id])

    IMAGE_TYPES = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'}

    @property
    def is_image(self):
        return (self.file_type or '').lower() in self.IMAGE_TYPES

    @property
    def size_human(self):
        """Tamaño legible (B, KB, MB...)"""
        size = float(self.file_size or 0)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{int(size)} {unit}" if unit == 'B' else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def viewer_kind(self):
        """Tipo de visor interno: 'image', 'pdf', 'text', 'markdown' o None"""
        ext = (self.file_type or '').lower()
        if self.is_image:
            return 'image'
        if ext == 'pdf':
            return 'pdf'
        if ext == 'md':
            return 'markdown'
        if ext in {'txt', 'csv'}:
            return 'text'
        return None

    @property
    def icon(self):
        """Icono de Bootstrap Icons según el tipo de archivo"""
        ext = (self.file_type or '').lower()
        if self.is_image:
            return 'bi-file-earmark-image'
        return {
            'pdf': 'bi-file-earmark-pdf',
            'doc': 'bi-file-earmark-word', 'docx': 'bi-file-earmark-word',
            'xls': 'bi-file-earmark-excel', 'xlsx': 'bi-file-earmark-excel', 'csv': 'bi-file-earmark-spreadsheet',
            'ppt': 'bi-file-earmark-ppt', 'pptx': 'bi-file-earmark-ppt',
            'txt': 'bi-file-earmark-text', 'md': 'bi-file-earmark-text',
            'zip': 'bi-file-earmark-zip', 'rar': 'bi-file-earmark-zip',
        }.get(ext, 'bi-file-earmark')
