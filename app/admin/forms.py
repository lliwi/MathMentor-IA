"""
Admin forms
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, SubmitField, PasswordField, RadioField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, URL, NumberRange


class UploadBookForm(FlaskForm):
    """Form for uploading a book PDF"""
    title = StringField('Título del Libro', validators=[DataRequired()])
    course = StringField('Curso', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 1º ESO, 2º Bachillerato"})
    subject = StringField('Materia', validators=[DataRequired()],
                         render_kw={"placeholder": "Ej: Matemáticas, Física"})
    pdf_file = FileField('Archivo PDF', validators=[
        FileRequired(),
        FileAllowed(['pdf'], 'Solo archivos PDF permitidos')
    ])
    submit = SubmitField('Subir y Procesar')


class EditBookForm(FlaskForm):
    """Form for editing book metadata"""
    title = StringField('Título del Libro', validators=[DataRequired()])
    course = StringField('Curso', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 1º ESO, 2º Bachillerato"})
    subject = StringField('Materia', validators=[DataRequired()],
                         render_kw={"placeholder": "Ej: Matemáticas, Física"})
    submit = SubmitField('Guardar Cambios')


class AssignTopicsForm(FlaskForm):
    """Form for assigning topics to a student"""
    student_id = SelectField('Estudiante', coerce=int, validators=[DataRequired()])
    topics = SelectField('Temas', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Asignar Temas')


class CreateStudentForm(FlaskForm):
    """Form for creating a new student"""
    username = StringField('Nombre de Usuario', validators=[
        DataRequired(),
        Length(min=3, max=80, message='El nombre de usuario debe tener entre 3 y 80 caracteres')
    ], render_kw={"placeholder": "usuario_estudiante"})

    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Email inválido')
    ], render_kw={"placeholder": "estudiante@email.com"})

    password = PasswordField('Contraseña', validators=[
        DataRequired(),
        Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
    ])

    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(),
        EqualTo('password', message='Las contraseñas deben coincidir')
    ])

    course = StringField('Curso', validators=[Optional()],
                        render_kw={"placeholder": "Ej: 1º ESO, 2º Bachillerato"})

    submit = SubmitField('Crear Estudiante')


class EditStudentForm(FlaskForm):
    """Form for editing student information"""
    username = StringField('Nombre de Usuario', validators=[
        DataRequired(),
        Length(min=3, max=80, message='El nombre de usuario debe tener entre 3 y 80 caracteres')
    ])

    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Email inválido')
    ])

    course = StringField('Curso', validators=[Optional()],
                        render_kw={"placeholder": "Ej: 1º ESO, 2º Bachillerato"})

    password = PasswordField('Nueva Contraseña (dejar en blanco para no cambiar)', validators=[
        Optional(),
        Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
    ])

    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        EqualTo('password', message='Las contraseñas deben coincidir')
    ])

    submit = SubmitField('Guardar Cambios')


class AddYouTubeChannelForm(FlaskForm):
    """Form for adding a YouTube channel"""
    channel_url = StringField('URL del Canal de YouTube', validators=[
        DataRequired(message='La URL del canal es requerida'),
        URL(message='Debe ser una URL válida')
    ], render_kw={"placeholder": "https://www.youtube.com/@nombrecanal"})

    course = StringField('Curso', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 1º ESO, 2º Bachillerato"})

    subject = StringField('Materia', validators=[Optional()],
                         default="Matemáticas",
                         render_kw={"placeholder": "Matemáticas"})

    submit = SubmitField('Importar Videos Seleccionados')
