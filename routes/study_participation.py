from flask import Blueprint, render_template, request, jsonify, session, current_app, abort, url_for, redirect
from models.study import Study
from models.response import StudyResponse, TaskSession, CompletedTask, ClassificationAnswer, ElementInteraction
from datetime import datetime
import uuid
import json

study_participation_bp = Blueprint('study_participation', __name__, url_prefix='/study')

@study_participation_bp.route('/<share_token>')
def study_welcome(share_token):
    """Study welcome page for anonymous respondents."""
    study = Study.objects(share_token=share_token).first()
    if not study:
        abort(404)
    
    if study.status != 'active':
        return render_template('study_participation/study_inactive.html', study=study)
    
    # Check if user already has a session
    if 'study_session_id' in session and session['study_session_id']:
        return redirect(url_for('study_participation.study_orientation', share_token=share_token))
    
    return render_template('study_participation/welcome.html', study=study)

@study_participation_bp.route('/<share_token>/start', methods=['POST'])
def start_study(share_token):
    """Start study participation and assign respondent ID."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        return jsonify({'error': 'Study not found or inactive'}), 404
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Get next available respondent ID
    respondent_id = study.get_available_respondent_id()
    if respondent_id is None:
        return jsonify({'error': 'Study is full'}), 400
    
    # Create study response
    study_response = StudyResponse(
        study=study,
        session_id=session_id,
        respondent_id=respondent_id,
        total_tasks_assigned=study.iped_parameters.tasks_per_consumer,
        session_start_time=datetime.utcnow(),
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', ''),
        browser_info={
            'accept_language': request.headers.get('Accept-Language', ''),
            'accept_encoding': request.headers.get('Accept-Encoding', ''),
            'user_agent': request.headers.get('User-Agent', '')
        }
    )
    study_response.save()
    
    # Update study statistics
    study.total_responses += 1
    study.save()
    
    # Store session info
    session['study_session_id'] = session_id
    session['study_share_token'] = share_token
    session['respondent_id'] = respondent_id
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'respondent_id': respondent_id,
        'redirect_url': url_for('study_participation.classification_questions', share_token=share_token)
    })

@study_participation_bp.route('/<share_token>/personal-info')
def personal_info(share_token):
    """Personal information page."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        abort(404)
    
    session_id = session.get('study_session_id')
    if not session_id:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    return render_template('study_participation/personal_info.html', 
                         study=study, study_response=study_response)

@study_participation_bp.route('/<share_token>/personal-info/submit', methods=['POST'])
def submit_personal_info(share_token):
    """Submit personal information."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        return jsonify({'error': 'Study not found or inactive'}), 404
    
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return jsonify({'error': 'Study response not found'}), 400
    
    # Save personal information
    personal_info = {
        'age': request.form.get('age'),
        'gender': request.form.get('gender'),
        'education': request.form.get('education')
    }
    
    study_response.personal_info = personal_info
    study_response.save()
    
    return jsonify({
        'success': True,
        'redirect_url': url_for('study_participation.classification_questions', share_token=share_token)
    })

@study_participation_bp.route('/<share_token>/classification')
def classification_questions(share_token):
    """Classification questions page."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        abort(404)
    
    session_id = session.get('study_session_id')
    if not session_id:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    return render_template('study_participation/classification.html', 
                         study=study, study_response=study_response)

@study_participation_bp.route('/<share_token>/classification/submit', methods=['POST'])
def submit_classification(share_token):
    """Submit classification answers."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        return jsonify({'error': 'Study not found or inactive'}), 404
    
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return jsonify({'error': 'Study response not found'}), 400
    
    try:
        data = request.get_json()
        answers = data.get('answers', [])
        
        # Process classification answers
        for answer_data in answers:
            answer = ClassificationAnswer(
                question_id=answer_data['question_id'],
                question_text=answer_data['question_text'],
                question_type=answer_data['question_type'],
                answer=answer_data['answer'],
                answer_timestamp=datetime.utcnow(),
                time_spent_seconds=answer_data.get('time_spent', 0.0)
            )
            study_response.classification_answers.append(answer)
        
        study_response.save()
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('study_participation.task_page', share_token=share_token, task_index=0)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@study_participation_bp.route('/<share_token>/orientation')
def study_orientation(share_token):
    """Study orientation page."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        abort(404)
    
    session_id = session.get('study_session_id')
    if not session_id:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    return render_template('study_participation/orientation.html', 
                         study=study, study_response=study_response)

@study_participation_bp.route('/<share_token>/task/<int:task_index>')
def task_page(share_token, task_index):
    """Individual task page."""
    study = Study.objects(share_token=share_token).first()
    if not study or study.status != 'active':
        abort(404)
    
    session_id = session.get('study_session_id')
    if not session_id:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    # Get respondent's tasks
    respondent_tasks = study.get_respondent_tasks(study_response.respondent_id)
    if not respondent_tasks or task_index >= len(respondent_tasks):
        abort(404)
    
    current_task = respondent_tasks[task_index]
    
    # Get visible elements for this task
    visible_elements = []
    for element in study.elements:
        if current_task['elements_shown'].get(element.element_id, 0) == 1:
            visible_elements.append(element)
    
    return render_template('study_participation/task.html',
                         study=study,
                         study_response=study_response,
                         current_task=current_task,
                         visible_elements=visible_elements,
                         task_index=task_index,
                         total_tasks=len(respondent_tasks))

@study_participation_bp.route('/<share_token>/task/<int:task_index>/start', methods=['POST'])
def start_task(share_token, task_index):
    """Start timing for a specific task."""
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return jsonify({'error': 'Study response not found'}), 400
    
    study = study_response.study
    
    # Get respondent's tasks
    respondent_tasks = study.get_respondent_tasks(study_response.respondent_id)
    if not respondent_tasks or task_index >= len(respondent_tasks):
        return jsonify({'error': 'Invalid task index'}), 400
    
    current_task = respondent_tasks[task_index]
    
    # Create or update task session
    task_session = TaskSession.objects(
        session_id=session_id,
        task_id=current_task['task_id']
    ).first()
    
    if not task_session:
        task_session = TaskSession(
            session_id=session_id,
            task_id=current_task['task_id'],
            study_response=study_response
        )
        task_session.add_page_transition('task_start')
        task_session.save()
    
    # Update study response
    study_response.current_task_index = task_index
    study_response.last_activity = datetime.utcnow()
    study_response.save()
    
    return jsonify({
        'success': True,
        'task_id': current_task['task_id'],
        'start_time': datetime.utcnow().isoformat()
    })

@study_participation_bp.route('/<share_token>/task/<int:task_index>/complete', methods=['POST'])
def complete_task(share_token, task_index):
    """Complete a task and submit rating."""
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return jsonify({'error': 'Study response not found'}), 400
    
    study = study_response.study
    
    try:
        data = request.get_json()
        rating = data.get('rating')
        task_start_time = datetime.fromisoformat(data.get('task_start_time'))
        element_interactions = data.get('element_interactions', [])
        
        if not rating:
            return jsonify({'error': 'Rating is required'}), 400
        
        # Get respondent's tasks
        respondent_tasks = study.get_respondent_tasks(study_response.respondent_id)
        if not respondent_tasks or task_index >= len(respondent_tasks):
            return jsonify({'error': 'Invalid task index'}), 400
        
        current_task = respondent_tasks[task_index]
        task_completion_time = datetime.utcnow()
        task_duration = (task_completion_time - task_start_time).total_seconds()
        
        # Create completed task record
        completed_task_data = {
            'task_id': current_task['task_id'],
            'respondent_id': study_response.respondent_id,
            'task_index': task_index,
            'elements_shown_in_task': current_task['elements_shown'],
            'task_start_time': task_start_time,
            'task_completion_time': task_completion_time,
            'task_duration_seconds': task_duration,
            'rating_given': rating,
            'rating_timestamp': task_completion_time,
            'element_interactions': []
        }
        
        # Process element interactions
        for interaction_data in element_interactions:
            interaction = ElementInteraction(
                element_id=interaction_data['element_id'],
                view_time_seconds=interaction_data.get('view_time', 0.0),
                hover_count=interaction_data.get('hover_count', 0),
                click_count=interaction_data.get('click_count', 0),
                first_view_time=datetime.fromisoformat(interaction_data.get('first_view_time')) if interaction_data.get('first_view_time') else None,
                last_view_time=datetime.fromisoformat(interaction_data.get('last_view_time')) if interaction_data.get('last_view_time') else None
            )
            completed_task_data['element_interactions'].append(interaction)
        
        # Add completed task to study response
        study_response.add_completed_task(completed_task_data)
        study_response.save()
        
        # Update task session
        task_session = TaskSession.objects(
            session_id=session_id,
            task_id=current_task['task_id']
        ).first()
        
        if task_session:
            task_session.mark_completed()
            task_session.save()
        
        # Check if study is completed
        if study_response.completed_tasks_count >= study_response.total_tasks_assigned:
            study_response.mark_completed()
            study_response.save()
            
            # Update study statistics
            study.completed_responses += 1
            study.save()
            
            return jsonify({
                'success': True,
                'study_completed': True,
                'redirect_url': url_for('study_participation.study_completed', share_token=share_token)
            })
        
        # Move to next task
        next_task_index = task_index + 1
        if next_task_index < len(respondent_tasks):
            return jsonify({
                'success': True,
                'study_completed': False,
                'redirect_url': url_for('study_participation.task_page', 
                                      share_token=share_token, task_index=next_task_index)
            })
        else:
            # All tasks completed
            study_response.mark_completed()
            study_response.save()
            
            study.completed_responses += 1
            study.save()
            
            return jsonify({
                'success': True,
                'study_completed': True,
                'redirect_url': url_for('study_participation.study_completed', share_token=share_token)
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@study_participation_bp.route('/<share_token>/completed')
def study_completed(share_token):
    """Study completion page."""
    study = Study.objects(share_token=share_token).first()
    if not study:
        abort(404)
    
    session_id = session.get('study_session_id')
    if not session_id:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return redirect(url_for('study_participation.study_welcome', share_token=share_token))
    
    # Clear session
    session.pop('study_session_id', None)
    session.pop('study_share_token', None)
    session.pop('respondent_id', None)
    
    return render_template('study_participation/completed.html', 
                         study=study, study_response=study_response)

@study_participation_bp.route('/<share_token>/abandon', methods=['POST'])
def abandon_study(share_token):
    """Abandon study participation."""
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    study_response = StudyResponse.objects(session_id=session_id).first()
    if not study_response:
        return jsonify({'error': 'Study response not found'}), 400
    
    try:
        data = request.get_json()
        reason = data.get('reason', 'User abandoned study')
        
        # Mark as abandoned
        study_response.mark_abandoned(reason)
        study_response.save()
        
        # Update study statistics
        study = study_response.study
        study.abandoned_responses += 1
        study.save()
        
        # Clear session
        session.pop('study_session_id', None)
        session.pop('study_share_token', None)
        session.pop('respondent_id', None)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@study_participation_bp.route('/<share_token>/tracking', methods=['POST'])
def track_interaction(share_token):
    """Track element interactions and timing."""
    session_id = session.get('study_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    try:
        data = request.get_json()
        interaction_type = data.get('type')  # 'view', 'hover', 'click'
        element_id = data.get('element_id')
        duration = data.get('duration', 0.0)
        
        if not interaction_type or not element_id:
            return jsonify({'error': 'Missing interaction data'}), 400
        
        # Find task session
        task_session = TaskSession.objects(session_id=session_id).order_by('-created_at').first()
        if task_session:
            task_session.add_element_interaction(element_id, interaction_type, duration)
            task_session.save()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
