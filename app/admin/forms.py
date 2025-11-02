"""
Admin forms
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


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
