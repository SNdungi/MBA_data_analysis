import os
import click
import toml
from flask.cli import with_appcontext
from flask import current_app

from app.app_database.extensions import db
# Import User and Role models (Adjust path if your models are in encoder_models)
from app.app_database.encoder_models import User, Role 
from app.app_database.tutorials_models import (
    TutorialLevel,
    TutorialSection,
    TutorialTopic,
    TutorialSubtopic
)

# -----------------------------------------------------------------------------
# COMMAND: CREATE ADMIN
# -----------------------------------------------------------------------------
@click.command("create_admin")
@click.option("--email", prompt="Admin Email", help="The email address for the admin account.")
@click.option("--username", prompt="Admin Username", help="The username for the admin account.")
@click.password_option(help="The password for the admin account.")
@with_appcontext
def create_admin(email, username, password):
    """
    Create or promote a user to Admin privileges.
    Requires the ADMIN_INIT_PW environment variable to be set and matched.
    """
    
    # 1. SECURITY CHECK
    # Check if the environment variable exists
    env_key = os.environ.get("ADMIN_INIT_PW")
    
    if not env_key:
        click.echo(click.style("CRITICAL ERROR: ADMIN_INIT_PW is not set in .env file.", fg="red", bold=True))
        click.echo("This security variable is required to create administrative accounts.")
        return

    # Prompt user to prove they know the key
    user_input_key = click.prompt("Enter the System Initialization Key (ADMIN_INIT_PW)", hide_input=True)

    if user_input_key != env_key:
        click.echo(click.style("ACCESS DENIED: Incorrect Initialization Key.", fg="red", bold=True))
        return

    # 2. ENSURE ROLE EXISTS
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        click.echo("Admin role missing. Creating 'Admin' role...")
        admin_role = Role(name='Admin', description='System Administrator')
        db.session.add(admin_role)
        db.session.flush() # Flush to get ID

    # 3. CHECK USER EXISTENCE
    user = User.query.filter((User.email == email) | (User.username == username)).first()

    if user:
        if user.role and user.role.name == 'Admin':
            click.echo(click.style(f"User '{user.username}' is already an Admin. Updating password...", fg="yellow"))
        else:
            click.echo(click.style(f"User '{user.username}' exists. Promoting to Admin...", fg="yellow"))
        
        # Update details
        user.email = email
        user.username = username
        user.role = admin_role
        user.set_password(password)
    else:
        # Create New User
        click.echo(click.style(f"Creating new Admin user: {username}...", fg="green"))
        user = User(username=username, email=email)
        user.set_password(password)
        user.role = admin_role
        db.session.add(user)

    # 4. COMMIT
    try:
        db.session.commit()
        click.echo(click.style(f"✅ Success! User '{username}' is now an Administrator.", fg="green", bold=True))
    except Exception as e:
        db.session.rollback()
        click.echo(click.style(f"❌ Database Error: {e}", fg="red"))


# -----------------------------------------------------------------------------
# COMMAND: SEED TUTORIALS
# -----------------------------------------------------------------------------
@click.command("seed_tutorials")
@with_appcontext
def seed_tutorials():
    """Seed tutorial levels, sections, topics, and subtopics from TOML file."""

    # Get base directory from app config
    base_dir = current_app.config.get('BASE_DIR', os.getcwd())

    # Full path to config.toml
    path = os.path.join(base_dir, "config.toml")

    if not os.path.exists(path):
        click.echo(f"❌ config.toml not found at: {path}")
        return

    try:
        data = toml.load(path)
        
        count = 0
        for level_data in data.get("levels", []):
            # Check if exists or create
            level = TutorialLevel.query.filter_by(title=level_data["title"]).first()
            if not level:
                level = TutorialLevel(
                    title=level_data["title"],
                    description=level_data.get("description")
                )
                db.session.add(level)
                db.session.flush() # Flush to get ID

            for section_data in level_data.get("sections", []):
                section = TutorialSection.query.filter_by(title=section_data["title"], level_id=level.id).first()
                if not section:
                    section = TutorialSection(
                        title=section_data["title"],
                        description=section_data.get("description"),
                        level=level
                    )
                    db.session.add(section)
                    db.session.flush()

                for topic_data in section_data.get("topics", []):
                    topic = TutorialTopic.query.filter_by(title=topic_data["title"], section_id=section.id).first()
                    if not topic:
                        topic = TutorialTopic(
                            title=topic_data["title"],
                            description=topic_data.get("description"),
                            section=section
                        )
                        db.session.add(topic)
                        db.session.flush()

                    for sub_data in topic_data.get("subtopics", []):
                        
                        # --- FIX: ROBUST EXAMPLE HANDLING ---
                        raw_examples = sub_data.get("examples", {})
                        
                        # Ensure examples_data is a dictionary so we can add 'images' to it
                        if isinstance(raw_examples, list):
                            # If it's a list, wrap it in a dict key
                            examples_data = {"list_content": raw_examples}
                        elif isinstance(raw_examples, dict):
                            examples_data = raw_examples.copy() # Copy to avoid mutating original
                        else:
                            # Handle strings/other types
                            examples_data = {"content": raw_examples}

                        # Now it is safe to add images if they exist
                        if "images" in sub_data:
                            examples_data['images'] = sub_data['images']
                        # ------------------------------------

                        # Check if subtopic exists to avoid duplicates
                        existing_sub = TutorialSubtopic.query.filter_by(title=sub_data["title"], topic_id=topic.id).first()
                        if not existing_sub:
                            subtopic = TutorialSubtopic(
                                title=sub_data["title"],
                                short_description=sub_data.get("description"), 
                                definition_text=sub_data.get("definition"),
                                video_url=sub_data.get("video_link"), 
                                examples=examples_data,
                                topic=topic
                            )
                            db.session.add(subtopic)
                            count += 1

        db.session.commit()
        click.echo(f"✅ Tutorial content seeded successfully! ({count} new subtopics created)")

    except Exception as e:
        db.session.rollback()
        # Print full error for debugging
        import traceback
        traceback.print_exc()
        click.echo(f"❌ Error seeding tutorials: {e}")