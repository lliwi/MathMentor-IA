"""
Authentication routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.auth import auth_bp
from app.models.user import User
from app import db


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')

            if not next_page:
                if user.role == 'admin':
                    next_page = url_for('admin.dashboard')
                else:
                    next_page = url_for('student.dashboard')

            return redirect(next_page)
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Logout route"""
    logout_user()
    flash('Has cerrado sesión exitosamente', 'success')
    return redirect(url_for('auth.login'))
