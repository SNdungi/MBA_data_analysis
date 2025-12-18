from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.app_database.encoder_models import db, User
from urllib.parse import urlparse 
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager

auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('file_mgt.list_projects'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        
        # Handle the "next" url argument if it exists
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('file_mgt.list_projects')
            
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign In')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('file_mgt.list_projects'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('password_confirm')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'warning')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'warning')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(email=email, username=username)
        new_user.set_password(password)
        new_user.generate_user_code()
        
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', title='Register')

@auth_bp.route('/logout')
@login_required
def logout():
    # 1. Clean up the temp file system for this user
    WorkspaceManager.cleanup_user_session(current_user.id)
    
    # 2. Log out
    logout_user()
    flash('You have been logged out and your temporary workspace cleared.', 'info')
    return redirect(url_for('auth.login'))