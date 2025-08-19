from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
from models.study import Study, RatingScale, StudyElement, ClassificationQuestion, IPEDParameters
from models.study_draft import StudyDraft
from forms.study import (
    Step1aBasicDetailsForm, Step1bStudyTypeForm, Step1cRatingScaleForm,
    Step2cIPEDParametersForm, Step3aTaskGenerationForm, Step3bLaunchForm
)
from utils.azure_storage import upload_to_azure, is_valid_image_file, get_file_size_mb

study_creation_bp = Blueprint('study_creation', __name__, url_prefix='/study/create')

def get_study_draft():
    """Get or create study creation draft in database."""
    # Try to get existing draft
    draft = StudyDraft.objects(user=current_user, is_complete=False).order_by('-created_at').first()
    
    if not draft:
        # Create new draft
        draft = StudyDraft(user=current_user, current_step='1a')
        draft.save()
    
    return draft

def save_uploaded_file(file, study_id):
    """Save uploaded file to Azure Blob Storage and return URL."""
    if file and file.filename:
        # Validate file type
        if not is_valid_image_file(file.filename):
            return None
        
        # Check file size (max 16MB)
        file_size_mb = get_file_size_mb(file)
        if file_size_mb > 16:
            return None
        
        # Upload to Azure
        azure_url = upload_to_azure(file)
        return azure_url
    return None

@study_creation_bp.route('/')
@login_required
def index():
    """Study creation index - redirect to first step."""
    return redirect(url_for('study_creation.step1a'))

@study_creation_bp.route('/step1a', methods=['GET', 'POST'])
@login_required
def step1a():
    """Step 1a: Basic Study Details."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('1a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.index'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('1a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.index'))
    
    form = Step1aBasicDetailsForm()
    if form.validate_on_submit():
        draft.update_step_data('1a', {
            'title': form.title.data,
            'background': form.background.data,
            'language': form.language.data,
            'terms_accepted': form.terms_accepted.data
        })
        draft.current_step = '1b'
        draft.save()
        flash('Basic details saved successfully!', 'success')
        return redirect(url_for('study_creation.step1b'))
    
    # Pre-populate form if data exists
    step_data = draft.get_step_data('1a')
    if step_data:
        form.title.data = step_data.get('title', '')
        form.background.data = step_data.get('background', '')
        form.language.data = step_data.get('language', 'en')
        form.terms_accepted.data = step_data.get('terms_accepted', False)
    
    return render_template('study_creation/step1a.html', form=form, current_step='1a')

@study_creation_bp.route('/step1b', methods=['GET', 'POST'])
@login_required
def step1b():
    """Step 1b: Study Type & Main Question."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('1b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1a'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('1b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1a'))
    
    form = Step1bStudyTypeForm()
    if form.validate_on_submit():
        draft.update_step_data('1b', {
            'study_type': form.study_type.data,
            'main_question': form.main_question.data,
            'orientation_text': form.orientation_text.data
        })
        draft.current_step = '1c'
        draft.save()
        flash('Study type and questions saved successfully!', 'success')
        return redirect(url_for('study_creation.step1c'))
    
    # Pre-populate form if data exists
    step_data = draft.get_step_data('1b')
    if step_data:
        form.study_type.data = step_data.get('study_type', 'image')
        form.main_question.data = step_data.get('main_question', '')
        form.orientation_text.data = step_data.get('orientation_text', '')
    
    return render_template('study_creation/step1b.html', form=form, current_step='1b')

@study_creation_bp.route('/step1c', methods=['GET', 'POST'])
@login_required
def step1c():
    """Step 1c: Rating Scale Configuration."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('1c'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1b'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('1c'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1b'))
    
    form = Step1cRatingScaleForm()
    if form.validate_on_submit():
        draft.update_step_data('1c', {
            'min_value': form.min_value.data,
            'max_value': form.max_value.data,
            'min_label': form.min_label.data,
            'max_label': form.max_label.data,
            'middle_label': form.middle_label.data
        })
        draft.current_step = '2a'
        draft.save()
        flash('Rating scale configuration saved successfully!', 'success')
        return redirect(url_for('study_creation.step2a'))
    
    # Pre-populate form if data exists
    step_data = draft.get_step_data('1c')
    if step_data:
        form.min_value.data = step_data.get('min_value', 1)
        form.max_value.data = step_data.get('max_value', 5)
        form.min_label.data = step_data.get('min_label', '')
        form.max_label.data = step_data.get('max_label', '')
        form.middle_label.data = step_data.get('middle_label', '')
    
    return render_template('study_creation/step1c.html', form=form, current_step='1c')

@study_creation_bp.route('/step2a', methods=['GET', 'POST'])
@login_required
def step2a():
    """Step 2a: Study Elements Setup."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('2a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1c'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('2a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step1c'))
    
    study_type = draft.get_step_data('1b').get('study_type', 'image')
    
    if request.method == 'POST':
        # Handle dynamic form submission
        elements_data = []
        num_elements = int(request.form.get('num_elements', 4))
        
        for i in range(num_elements):
            element_data = {
                'element_id': f"E{i+1}",
                'name': request.form.get(f'element_{i}_name', ''),
                'description': request.form.get(f'element_{i}_description', ''),
                'alt_text': request.form.get(f'element_{i}_alt_text', '')
            }
            
            if study_type == 'image':
                # Handle image file upload to Azure
                file = request.files.get(f'element_{i}_image')
                current_image = request.form.get(f'element_{i}_current_image', '')
                
                if file and file.filename:
                    # New image uploaded - upload to Azure and get URL
                    azure_url = save_uploaded_file(file, f"element_{i}")
                    if azure_url:
                        element_data['content'] = azure_url
                        element_data['element_type'] = 'image'
                    else:
                        flash(f'Failed to upload image for element {i+1}. Please check file type and size.', 'error')
                        return render_template('study_creation/step2a.html', 
                                            study_type=study_type, num_elements=num_elements, 
                                            elements_data=elements_data, current_step='2a')
                elif current_image:
                    # No new image, but current image exists - keep the current image
                    element_data['content'] = current_image
                    element_data['element_type'] = 'image'
                else:
                    # No image at all - this is required for image-based studies
                    flash(f'Image file is required for element {i+1}', 'error')
                    return render_template('study_creation/step2a.html', 
                                        study_type=study_type, num_elements=num_elements, 
                                        elements_data=elements_data, current_step='2a')
            else:
                element_data['content'] = request.form.get(f'element_{i}_content', '')
                element_data['element_type'] = 'text'
            
            elements_data.append(element_data)
        
        draft.update_step_data('2a', {
            'elements': elements_data,
            'study_type': study_type,
            'num_elements': num_elements
        })
        draft.current_step = '2b'
        draft.save()
        flash('Study elements saved successfully!', 'success')
        return redirect(url_for('study_creation.step2b'))
    
    # Get number of elements from form or previous data or default
    if request.args.get('num_elements'):
        num_elements = int(request.args.get('num_elements'))
    else:
        # Try to get from existing step2a data
        existing_data = draft.get_step_data('2a')
        if existing_data and 'elements' in existing_data:
            # Prioritize the stored num_elements value over the existing elements count
            stored_num_elements = existing_data.get('num_elements', 4)
            existing_count = len(existing_data['elements'])
            # Use stored num_elements if it exists, otherwise use the larger of existing count or default
            num_elements = stored_num_elements if stored_num_elements > 0 else max(existing_count, 4)
        else:
            num_elements = 4
    elements_data = draft.get_step_data('2a').get('elements', []) if draft.get_step_data('2a') else []
    
    # Debug logging
    print(f"DEBUG: num_elements = {num_elements}")
    print(f"DEBUG: elements_data length = {len(elements_data) if elements_data else 0}")
    print(f"DEBUG: existing_data = {draft.get_step_data('2a')}")
    
    return render_template('study_creation/step2a.html', 
                         study_type=study_type, num_elements=num_elements, 
                         elements_data=elements_data, current_step='2a')

@study_creation_bp.route('/step2b', methods=['GET', 'POST'])
@login_required
def step2b():
    """Step 2b: Classification Questions."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('2b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2a'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('2b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2a'))
    
    if request.method == 'POST':
        # Handle dynamic form submission
        questions_data = []
        num_questions = int(request.form.get('num_questions', 2))
        
        for i in range(num_questions):
            question_data = {
                'question_id': f"Q{i+1}",
                'question_text': request.form.get(f'question_{i}_text', ''),
                'question_type': request.form.get(f'question_{i}_type', 'single_choice'),
                'answer_options': request.form.get(f'question_{i}_options', '').split('\n') if request.form.get(f'question_{i}_options') else [],
                'is_required': request.form.get(f'question_{i}_required') == 'on',
                'order': i + 1
            }
            questions_data.append(question_data)
        
        draft.update_step_data('2b', {
            'questions': questions_data
        })
        draft.current_step = '2c'
        draft.save()
        flash('Classification questions saved successfully!', 'success')
        return redirect(url_for('study_creation.step2c'))
    
    # Pre-populate from stored data if available
    stored_step2b = draft.get_step_data('2b') or {}
    if stored_step2b and stored_step2b.get('questions'):
        num_questions = len(stored_step2b['questions'])
        questions_data = stored_step2b['questions']
    else:
        num_questions = 2
        questions_data = []
    
    return render_template('study_creation/step2b.html', 
                         num_questions=num_questions, questions_data=questions_data, current_step='2b')

@study_creation_bp.route('/step2c', methods=['GET', 'POST'])
@login_required
def step2c():
    """Step 2c: IPED Parameters."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('2c'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2b'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('2c'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2b'))
    
    form = Step2cIPEDParametersForm()
    
    # Pre-populate from DB if available; otherwise set sensible defaults
    stored_step2c = draft.get_step_data('2c') or {}
    if request.method == 'GET':
        if stored_step2c:
            form.num_elements.data = stored_step2c.get('num_elements')
            form.tasks_per_consumer.data = stored_step2c.get('tasks_per_consumer')
            form.number_of_respondents.data = stored_step2c.get('number_of_respondents')
            form.min_active_elements.data = stored_step2c.get('min_active_elements')
            form.max_active_elements.data = stored_step2c.get('max_active_elements')
        else:
            # Set default values based on previous step elements count
            step2a_data = draft.get_step_data('2a')
            if step2a_data:
                form.num_elements.data = len(step2a_data.get('elements', []))
    
    if form.validate_on_submit():
        draft.update_step_data('2c', {
            'num_elements': form.num_elements.data,
            'tasks_per_consumer': form.tasks_per_consumer.data,
            'number_of_respondents': form.number_of_respondents.data,
            'min_active_elements': form.min_active_elements.data,
            'max_active_elements': form.max_active_elements.data,
            'total_tasks': form.tasks_per_consumer.data * form.number_of_respondents.data
        })
        draft.current_step = '3a'
        draft.save()
        flash('IPED parameters saved successfully!', 'success')
        return redirect(url_for('study_creation.step3a'))
    
    return render_template('study_creation/step2c.html', form=form, current_step='2c')

@study_creation_bp.route('/step3a', methods=['GET', 'POST'])
@login_required
def step3a():
    """Step 3a: IPED Task Matrix Generation."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('3a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2c'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('3a'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step2c'))
    
    form = Step3aTaskGenerationForm()
    
    # Pre-populate 3a state if stored
    stored_step3a = draft.get_step_data('3a') or {}
    if request.method == 'GET' and stored_step3a:
        if hasattr(form, 'regenerate_matrix'):
            form.regenerate_matrix.data = stored_step3a.get('regenerate_matrix', False)
    
    if form.validate_on_submit() or not draft.get_step_data('3a'):
        # Generate or regenerate task matrix
        try:
            # Create temporary study object to generate tasks
            temp_study = Study()
            step2c_data = draft.get_step_data('2c')
            temp_study.iped_parameters = IPEDParameters(
                num_elements=step2c_data['num_elements'],
                tasks_per_consumer=step2c_data['tasks_per_consumer'],
                number_of_respondents=step2c_data['number_of_respondents'],
                min_active_elements=step2c_data['min_active_elements'],
                max_active_elements=step2c_data['max_active_elements'],
                total_tasks=step2c_data['total_tasks']
            )
            
            # Generate task matrix
            tasks_matrix = temp_study.generate_tasks()
            
            draft.update_step_data('3a', {
                'tasks_matrix': tasks_matrix,
                'generated_at': datetime.utcnow().isoformat(),
                'regenerate_matrix': bool(getattr(form, 'regenerate_matrix', False) and form.regenerate_matrix.data)
            })
            draft.current_step = '3b'
            draft.save()
            
            flash('Task matrix generated successfully!', 'success')
            return redirect(url_for('study_creation.step3b'))
            
        except Exception as e:
            flash(f'Error generating task matrix: {str(e)}', 'error')
    
    # Show task matrix preview if available
    tasks_matrix = stored_step3a.get('tasks_matrix', {}) if stored_step3a else {}
    
    # Get step2c data for pre-population
    step2c_data = draft.get_step_data('2c') or {}
    
    # Calculate matrix summary statistics
    matrix_summary = {}
    if tasks_matrix:
        total_tasks = sum(len(tasks) for tasks in tasks_matrix.values())
        total_respondents = len(tasks_matrix)
        tasks_per_respondent = total_tasks // total_respondents if total_respondents > 0 else 0
        
        # Get elements per task from step2c data
        min_elements = step2c_data.get('min_active_elements', 0)
        max_elements = step2c_data.get('max_active_elements', 0)
        elements_per_task = f"{min_elements}-{max_elements}" if min_elements and max_elements else "-"
        
        matrix_summary = {
            'total_tasks': total_tasks,
            'total_respondents': total_respondents,
            'tasks_per_respondent': tasks_per_respondent,
            'elements_per_task': elements_per_task
        }
    
    return render_template('study_creation/step3a.html', 
                         form=form, tasks_matrix=tasks_matrix, 
                         step2c_data=step2c_data,
                         matrix_summary=matrix_summary,
                         current_step='3a')

@study_creation_bp.route('/step3b', methods=['GET', 'POST'])
@login_required
def step3b():
    """Step 3b: Study Preview & Launch."""
    draft = get_study_draft()
    
    if request.method == 'GET':
        # For GET requests (viewing/navigating), use can_access_step
        if not draft.can_access_step('3b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step3a'))
    else:
        # For POST requests (submitting), use can_proceed_to_step
        if not draft.can_proceed_to_step('3b'):
            flash('Please complete previous steps first.', 'warning')
            return redirect(url_for('study_creation.step3a'))
    
    form = Step3bLaunchForm()
    
    # Pre-populate from stored step3b data
    stored_step3b = draft.get_step_data('3b') or {}
    if request.method == 'GET' and stored_step3b:
        if hasattr(form, 'launch_study'):
            form.launch_study.data = stored_step3b.get('launch_study', False)
    
    if form.validate_on_submit():
        # Persist current 3b state in draft
        draft.update_step_data('3b', {
            'launch_study': bool(getattr(form, 'launch_study', False) and form.launch_study.data)
        })
        draft.save()
        try:
            # Create the study
            study = Study(
                title=draft.get_step_data('1a')['title'],
                background=draft.get_step_data('1a')['background'],
                language=draft.get_step_data('1a')['language'],
                main_question=draft.get_step_data('1b')['main_question'],
                orientation_text=draft.get_step_data('1b')['orientation_text'],
                study_type=draft.get_step_data('1b')['study_type'],
                creator=current_user,
                share_token=uuid.uuid4().hex,
                status='active'
            )
            
            # Set rating scale
            step1c_data = draft.get_step_data('1c')
            study.rating_scale = RatingScale(
                min_value=step1c_data['min_value'],
                max_value=step1c_data['max_value'],
                min_label=step1c_data['min_label'],
                max_label=step1c_data['max_label'],
                middle_label=step1c_data['middle_label']
            )
            
            # Set elements
            elements = []
            step2a_data = draft.get_step_data('2a')
            for element_data in step2a_data['elements']:
                element = StudyElement(
                    element_id=element_data['element_id'],
                    name=element_data['name'],
                    description=element_data.get('description', ''),
                    element_type=element_data['element_type'],
                    content=element_data['content'],
                    alt_text=element_data.get('alt_text', '')
                )
                elements.append(element)
            study.elements = elements
            
            # Set classification questions
            step2b_data = draft.get_step_data('2b')
            if step2b_data.get('questions'):
                questions = []
                for question_data in step2b_data['questions']:
                    question = ClassificationQuestion(
                        question_id=question_data['question_id'],
                        question_text=question_data['question_text'],
                        question_type=question_data['question_type'],
                        answer_options=question_data.get('answer_options', []),
                        is_required=question_data['is_required'],
                        order=question_data['order']
                    )
                    questions.append(question)
                study.classification_questions = questions
            
            # Set IPED parameters
            step2c_data = draft.get_step_data('2c')
            study.iped_parameters = IPEDParameters(
                num_elements=step2c_data['num_elements'],
                tasks_per_consumer=step2c_data['tasks_per_consumer'],
                number_of_respondents=step2c_data['number_of_respondents'],
                min_active_elements=step2c_data['min_active_elements'],
                max_active_elements=step2c_data['max_active_elements'],
                total_tasks=step2c_data['total_tasks']
            )
            
            # Set generated tasks
            step3a_data = draft.get_step_data('3a')
            study.tasks = step3a_data['tasks_matrix']
            
            # Generate share URL
            study.generate_share_url(request.host_url.rstrip('/'))
            
            # Save study
            study.save()
            
            # Update user's studies list
            current_user.studies.append(study)
            current_user.save()
            
            # Mark draft as complete and delete it
            draft.mark_complete()
            draft.delete()
            
            flash('Study created successfully!', 'success')
            return redirect(url_for('dashboard.study_detail', study_id=study._id))
            
        except Exception as e:
            flash(f'Error creating study: {str(e)}', 'error')
    
    # Prepare study preview data
    preview_data = {
        'step1a': draft.get_step_data('1a'),
        'step1b': draft.get_step_data('1b'),
        'step1c': draft.get_step_data('1c'),
        'step2a': draft.get_step_data('2a'),
        'step2b': draft.get_step_data('2b'),
        'step2c': draft.get_step_data('2c'),
        'step3a': draft.get_step_data('3a')
    }
    
    return render_template('study_creation/step3b.html', 
                         form=form, study_data=preview_data, current_step='3b')

@study_creation_bp.route('/reset')
@login_required
def reset():
    """Reset study creation draft."""
    draft = StudyDraft.objects(user=current_user, is_complete=False).order_by('-created_at').first()
    if draft:
        draft.delete()
    flash('Study creation draft reset. You can start over.', 'info')
    return redirect(url_for('study_creation.step1a'))

@study_creation_bp.route('/debug-draft')
@login_required
def debug_draft():
    """Debug draft data."""
    draft = StudyDraft.objects(user=current_user, is_complete=False).order_by('-created_at').first()
    if draft:
        return {
            'draft_exists': True,
            'draft_id': str(draft._id),
            'current_step': draft.current_step,
            'step1a_complete': bool(draft.step1a_data),
            'step1b_complete': bool(draft.step1b_data),
            'step1c_complete': bool(draft.step1c_data),
            'step2a_complete': bool(draft.step2a_data),
            'step2b_complete': bool(draft.step2b_data),
            'step2c_complete': bool(draft.step2c_data),
            'step3a_complete': bool(draft.step3a_data),
            'created_at': draft.created_at.isoformat() if draft.created_at else None,
            'updated_at': draft.updated_at.isoformat() if draft.updated_at else None
        }
    else:
        return {
            'draft_exists': False,
            'message': 'No draft found for current user'
        }
