from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, json


# The template_folder is set to 'templates' so we can use the 'encoding/' prefix in render_template calls.
tutorials_bp = Blueprint('tutorials', __name__, template_folder='templates/tutorials')

@tutorials_bp.route('/tutorials')
def index():
    sidebar_items = [
        {'name': 'Getting Started', 'url': '#'},
        {'name': 'Data Prep', 'url': '#'},
        {'name': 'Analytics', 'url': '#'},
        {'name': 'Advanced', 'url': '#'},
    ]
    return render_template('view_tutorials.html', sidebar_items=sidebar_items)