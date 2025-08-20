from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models.study import Study
from models.response import StudyResponse
from datetime import datetime
import uuid
import json

study_participation = Blueprint('study_participation', __name__)

@study_participation.route('/study/<study_id>/welcome')
def welcome(study_id):
    """Welcome page for study participation"""
    try:
        study = Study.objects.get(_id=study_id)
        
        
        if study.status != 'active':
            return render_template('study_participation/study_inactive.html', study=study)
        
        # Initialize session for this study
        session['study_id'] = str(study_id)
        session['current_step'] = 'welcome'
        session['study_data'] = {
            'personal_info': {},
            'classification_answers': [],
            'task_ratings': [],
            'start_time': datetime.utcnow().isoformat()
        }
        
        return render_template('study_participation/welcome.html', study=study)
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error starting study: {str(e)}', 'error')
        return redirect(url_for('index'))

@study_participation.route('/study/<study_id>/participate')
def participate(study_id):
    """Direct participation link - redirects to welcome"""
    return redirect(url_for('study_participation.welcome', study_id=study_id))

@study_participation.route('/participate/<share_token>')
def participate_by_token(share_token):
    """Access study participation by share token"""
    try:
        study = Study.objects.get(share_token=share_token)
        
        if study.status != 'active':
            return render_template('study_participation/study_inactive.html', study=study)
        
        # Redirect to welcome page with study ID
        return redirect(url_for('study_participation.welcome', study_id=str(study._id)))
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error accessing study: {str(e)}', 'error')
        return redirect(url_for('index'))

@study_participation.route('/study/<study_id>/personal-info', methods=['GET', 'POST'])
def personal_info(study_id):
    """Personal information collection page"""
    try:
        study = Study.objects.get(_id=study_id)
        
        if study.status != 'active':
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        if request.method == 'POST':
            # Get form data
            birth_date = request.form.get('birth_date')
            gender = request.form.get('gender')
            
            # Validate required fields
            if not birth_date or not gender:
                flash('Please fill in all required fields.', 'error')
                return render_template('study_participation/personal_info.html', study=study)
            
            # Calculate age from birth date
            try:
                birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d')
                age = (datetime.utcnow() - birth_date_obj).days // 365
                if age < 13 or age > 120:
                    flash('Please enter a valid age between 13 and 120.', 'error')
                    return render_template('study_participation/personal_info.html', study=study)
            except ValueError:
                flash('Please enter a valid birth date.', 'error')
                return render_template('study_participation/personal_info.html', study=study)
            
            # Store in session
            session['study_data']['personal_info'] = {
                'birth_date': birth_date,
                'age': age,
                'gender': gender
            }
            session['current_step'] = 'personal_info'
            
            # Redirect to classification questions
            return redirect(url_for('study_participation.classification', study_id=study_id))
        
        # Get today's date for max date validation
        today_date = datetime.utcnow().strftime('%Y-%m-%d')
        return render_template('study_participation/personal_info.html', study=study, today_date=today_date)
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('study_participation.welcome', study_id=study_id))

@study_participation.route('/study/<study_id>/classification', methods=['GET', 'POST'])
def classification(study_id):
    """Classification questions page"""
    try:
        study = Study.objects.get(_id=study_id)
        
        if study.status != 'active':
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Check if personal info is completed
        if not session.get('study_data', {}).get('personal_info'):
            return redirect(url_for('study_participation.personal_info', study_id=study_id))
        
        if request.method == 'POST':
            # Get classification answers
            answers = []
            for question in study.classification_questions:
                answer = request.form.get(f'classification_{question.question_id}')
                if answer:
                    answers.append({
                        'question_id': question.question_id,
                        'question_text': question.question_text,
                        'answer': answer,
                        'answer_timestamp': datetime.utcnow().isoformat(),
                        'time_spent_seconds': 0.0  # Will be calculated from frontend
                    })
            
            # Store in session
            session['study_data']['classification_answers'] = answers
            session['current_step'] = 'classification'
            
            # Redirect to first task
            return redirect(url_for('study_participation.task', study_id=study_id, task_number=1))
        
        return render_template('study_participation/classification.html', study=study)
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('study_participation.personal_info', study_id=study_id))

@study_participation.route('/study/<study_id>/task/<int:task_number>', methods=['GET', 'POST'])
def task(study_id, task_number):
    """Task interface page"""
    try:
        study = Study.objects.get(_id=study_id)
        
        if study.status != 'active':
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Check if previous steps are completed
        if not session.get('study_data', {}).get('personal_info'):
            return redirect(url_for('study_participation.personal_info', study_id=study_id))
        if not session.get('study_data', {}).get('classification_answers'):
            return redirect(url_for('study_participation.classification', study_id=study_id))
        
        # Get tasks from study - check if tasks exist
        if not hasattr(study, 'tasks') or not study.tasks:
            # Try to generate tasks if they don't exist
            try:
                if hasattr(study, 'generate_tasks'):
                    study.generate_tasks()
                    study.save()
                else:
                    flash('Study tasks not configured properly.', 'error')
                    return redirect(url_for('study_participation.welcome', study_id=study_id))
            except Exception as e:
                flash(f'Error generating tasks: {str(e)}', 'error')
                return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Check if tasks were generated
        if not hasattr(study, 'tasks') or not study.tasks:
            flash('Study tasks could not be generated.', 'error')
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Get total tasks from IPED parameters
        total_tasks = study.iped_parameters.tasks_per_consumer 
        
        if task_number < 1 or task_number > total_tasks:
            flash('Invalid task number.', 'error')
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Get the specific task data - tasks are organized by respondent_id
        # For anonymous participation, we'll use respondent_id 0
        respondent_tasks = study.tasks.get("0", [])
        if not respondent_tasks or task_number > len(respondent_tasks):
            flash('Task data not found.', 'error')
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        current_task = respondent_tasks[task_number - 1]
        
        # For GET requests, just render the task page
        # For POST requests (if any), handle them the same way
        # The actual rating submission is now handled via JavaScript and sessionStorage
        
        # Initialize task start time in session if not exists
        if 'task_start_times' not in session:
            session['task_start_times'] = {}
        
        session['task_start_times'][str(task_number)] = datetime.utcnow().isoformat()
        
        return render_template('study_participation/task.html', 
                           study=study, task_number=task_number, 
                           total_tasks=total_tasks, current_task=current_task)
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('study_participation.welcome', study_id=study_id))

@study_participation.route('/study/<study_id>/task-complete', methods=['POST'])
def task_complete(study_id):
    """Handle task completion data from sessionStorage"""
    try:
        study = Study.objects.get(_id=study_id)
        
        if study.status != 'active':
            return {'error': 'Study not active'}, 400
        
        # Get task data from request
        data = request.get_json()
        if not data:
            return {'error': 'No data provided'}, 400
        
        # Store task data in session
        task_ratings = session.get('study_data', {}).get('task_ratings', [])
        task_ratings.append({
            'task_number': data.get('task_number'),
            'rating': data.get('rating'),
            'timestamp': data.get('timestamp'),
            'task_start_time': data.get('task_start_time'),
            'task_end_time': data.get('task_end_time'),
            'task_duration_seconds': data.get('task_duration_seconds'),
            'task_data': data.get('task_data', {})
        })
        session['study_data']['task_ratings'] = task_ratings
        
        return {'success': True, 'message': 'Task data stored'}
        
    except Study.DoesNotExist:
        return {'error': 'Study not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

@study_participation.route('/study/<study_id>/completed')
def completed(study_id):
    """Study completion page"""
    try:
        study = Study.objects.get(_id=study_id)
        
        # Check if all data is available
        study_data = session.get('study_data', {})
        if not (study_data.get('personal_info') and 
                study_data.get('classification_answers') and 
                study_data.get('task_ratings')):
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
        # Create study response
        try:
            # Calculate total time spent
            start_time = datetime.fromisoformat(study_data['start_time'])
            completion_time = datetime.utcnow()
            total_time = (completion_time - start_time).total_seconds()
            
            # Create response with existing model structure
            response = StudyResponse(
                _id=str(uuid.uuid4()),
                study=study,
                session_id=str(uuid.uuid4()),
                respondent_id=1,  # Default respondent ID
                total_tasks_assigned=len(study_data['task_ratings']),
                completed_tasks_count=len(study_data['task_ratings']),
                session_start_time=start_time,
                session_end_time=completion_time,
                is_completed=True,
                classification_answers=study_data['classification_answers'],
                personal_info=study_data['personal_info'],
                total_study_duration=total_time,
                last_activity=completion_time
            )
            
            # Add completed tasks with proper timing data
            for task_rating in study_data['task_ratings']:
                # Get task timing from session if available
                task_start_time = None
                task_duration = 0.0
                
                if 'task_start_times' in session and str(task_rating['task_number']) in session['task_start_times']:
                    try:
                        task_start_time = datetime.fromisoformat(session['task_start_times'][str(task_rating['task_number'])])
                        # Calculate duration from the stored start time
                        if 'task_duration_seconds' in task_rating:
                            task_duration = task_rating['task_duration_seconds']
                        else:
                            # Fallback: calculate from start time to completion
                            task_duration = (completion_time - task_start_time).total_seconds()
                    except:
                        task_start_time = start_time  # Fallback
                        task_duration = 0.0
                else:
                    task_start_time = start_time  # Fallback
                    task_duration = 0.0
                
                task_data = {
                    'task_id': f"task_{task_rating['task_number']}",
                    'respondent_id': 1,
                    'task_index': task_rating['task_number'] - 1,
                    'elements_shown_in_task': task_rating['task_data'].get('elements_shown', {}),
                    'task_start_time': task_start_time,
                    'task_completion_time': completion_time,
                    'task_duration_seconds': task_duration,
                    'rating_given': task_rating['rating'],
                    'rating_timestamp': datetime.fromisoformat(task_rating['timestamp'])
                }
                response.add_completed_task(task_data)
            
            response.update_completion_percentage()
            response.save()
            
            # Clear session data
            session.pop('study_data', None)
            session.pop('study_id', None)
            session.pop('current_step', None)
            
            return render_template('study_participation/completed.html', study=study, response=response)
            
        except Exception as e:
            flash(f'Error saving response: {str(e)}', 'error')
            return redirect(url_for('study_participation.welcome', study_id=study_id))
        
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('study_participation.welcome', study_id=study_id))

@study_participation.route('/study/<study_id>/inactive')
def study_inactive(study_id):
    """Study inactive page"""
    try:
        study = Study.objects.get(_id=study_id)
        return render_template('study_participation/study_inactive.html', study=study)
    except Study.DoesNotExist:
        flash('Study not found.', 'error')
        return redirect(url_for('index'))
