from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.db import transaction # For atomic operations
from django.db.models import Q, Count, F # Import F for F expressions
from django import template
from django.contrib import messages
from django import forms
from datetime import date, timedelta
from django.utils import timezone
from django.db.models.functions import TruncMonth 
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.conf import settings 
import logging
logger = logging.getLogger(__name__)

from .models import (
    User, Patient, Doctor, Pharmacist, Appointment, Encounter, VitalSign, MedicalHistory,
    PhysicalExamination, Diagnosis, TreatmentPlan, LabTestRequest, LabTestResult, # LabTestRequest needed
    ImagingRequest, ImagingResult, Prescription, CaseSummary, ConsentForm, # Prescription, ImagingRequest needed
    Ward, Bed, Department, LabTest, ImagingType, Medication, Nurse, # Added Nurse
    CancerRegistryReport, BirthRecord, MortalityRecord, ProcurementOfficer,
    Receptionist, LabTechnician, Radiologist # Ensure these are imported if they are distinct profiles
)

from .forms import (
    CustomUserCreationForm, PatientRegistrationForm, AppointmentForm, VitalSignForm,
    MedicalHistoryForm, PhysicalExaminationForm, DiagnosisForm, TreatmentPlanForm,
    LabTestRequestForm, LabTestResultForm, ImagingRequestForm, ImagingResultForm,
    PrescriptionForm, ConsentFormForm, DoctorForm, DoctorRegistrationForm,
    NurseRegistrationForm, PharmacistRegistrationForm, ProcurementOfficerRegistrationForm,
    CustomUserChangeForm, ReceptionistRegistrationForm, LabTechnicianRegistrationForm, 
    RadiologistRegistrationForm 
)

from .models import ActivityLog
from django.contrib.auth.models import AnonymousUser
import json

# Utility function to get client IP address
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# --- Activity Log Function (Keep this at the top or in a separate utils.py) ---
def log_activity(user, action_type, description, model_name=None, object_id=None, ip_address=None, changes=None):
    if isinstance(user, AnonymousUser):
        user_obj = None
    else:
        user_obj = user

    ActivityLog.objects.create(
        user=user_obj,
        action_type=action_type,
        description=description,
        model_name=model_name,
        object_id=object_id,
        ip_address=ip_address,
        changes=json.dumps(changes) if changes else None # Store changes as JSON string
    )

# --- Mixins for Permissions ---

class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

class IsDoctorMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'doctor'

class IsNurseMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'nurse'

class IsPatientMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'patient'

class IsPharmacistMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'pharmacist'

class IsLabTechMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'lab_tech'

class IsRadiologistMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'radiologist'

class IsReceptionistMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'receptionist'

class IsProcurementOfficerMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'procurement_officer'

class IsMedicalStaffMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['doctor', 'nurse', 'lab_tech', 'radiologist', 'pharmacist', 'admin']

# --- Dashboard/Home Views ---

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'clinical_app/home.html' # Changed to dashboard.html for clarity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user_type'] = user.user_type if user.is_authenticated else 'anonymous'

        if user.is_authenticated:
            # Common date calculations for metrics
            current_datetime = timezone.now()
            thirty_days_ago = current_datetime - timedelta(days=30)
            today_start = timezone.make_aware(timezone.datetime.combine(timezone.now().date(), timezone.datetime.min.time()))
            today_end = timezone.make_aware(timezone.datetime.combine(timezone.now().date(), timezone.datetime.max.time()))
            one_year_ago = current_datetime - timedelta(days=365)

            if user.user_type == 'admin':
                context['total_patients'] = Patient.objects.count()
                context['total_doctors'] = Doctor.objects.count()
                context['pending_appointments'] = Appointment.objects.filter(status='scheduled').count()

                context['total_active_staff'] = User.objects.filter(is_active=True).exclude(user_type='patient').count()
                context['available_beds'] = Bed.objects.filter(is_occupied=False).count()
                context['total_departments'] = Department.objects.count()

                context['total_lab_tests_performed_last_30_days'] = LabTestResult.objects.filter(
                    result_date__gte=thirty_days_ago
                ).count()

                context['total_imaging_scans_performed_last_30_days'] = ImagingResult.objects.filter(
                    report_date__gte=thirty_days_ago
                ).count()

                context['medications_low_in_stock'] = Medication.objects.filter(
                    stock_quantity__lt=F('reorder_level')
                ).count()

                context['cancer_reports_unreported'] = CancerRegistryReport.objects.filter(
                    reported_to_registry=False,
                    report_date__gte=one_year_ago # Only consider reports from last year that haven't been submitted
                ).count()
                context['cancer_reports_submitted_last_30_days'] = CancerRegistryReport.objects.filter(
                    reported_to_registry=True,
                    registry_submission_date__gte=thirty_days_ago
                ).count()

                context['new_births_today'] = BirthRecord.objects.filter(
                    date_of_birth__gte=today_start,
                    date_of_birth__lte=today_end
                ).count()

                context['new_mortalities_today'] = MortalityRecord.objects.filter(
                    date_of_death__gte=today_start,
                    date_of_death__lte=today_end
                ).count()

                context['recent_activity_logs'] = ActivityLog.objects.select_related('user').order_by('-timestamp')[:5]
                # Patient Registrations over the last 12 months for Chart
                patient_registrations_monthly = Patient.objects.annotate(
                    month=TruncMonth('registration_date')
                ).values('month').annotate(
                    count=Count('pk') 
                ).order_by('month')

                reg_labels = [entry['month'].strftime('%b %Y') for entry in patient_registrations_monthly]
                reg_data = [entry['count'] for entry in patient_registrations_monthly]

                context['patient_reg_labels'] = reg_labels
                context['patient_reg_data'] = reg_data



            elif user.user_type == 'doctor':
                try:
                    doctor = user.doctor
                    context['my_appointments'] = Appointment.objects.filter(
                        doctor=doctor,
                        appointment_date__gte=timezone.now() # Upcoming appointments
                    ).order_by('appointment_date')[:5]
                    context['my_patients'] = Patient.objects.filter(
                        Q(encounters__doctor=doctor) | Q(appointments__doctor=doctor)
                    ).distinct().count()
                    context['recent_encounters'] = Encounter.objects.filter(
                        doctor=doctor
                    ).order_by('-encounter_date')[:5]
                except Doctor.DoesNotExist:
                    context['error'] = "Doctor profile not found. Please ensure your doctor profile is created."

            elif user.user_type == 'patient':
                try:
                    patient = user.patient
                    context['my_appointments'] = Appointment.objects.filter(
                        patient=patient,
                        appointment_date__gte=timezone.now() # Upcoming appointments
                    ).order_by('appointment_date')[:5]
                    context['my_recent_encounters'] = Encounter.objects.filter(
                        patient=patient
                    ).order_by('-encounter_date')[:5]
                except Patient.DoesNotExist:
                    context['error'] = "Patient profile not found. Please ensure your patient profile is created."

            elif user.user_type == 'pharmacist':
                try:
                    pharmacist = user.pharmacist
                    context['pending_prescriptions'] = Prescription.objects.filter(
                        is_dispensed=False
                    ).count()
                    context['low_stock_meds_pharmacist'] = Medication.objects.filter(
                        stock_quantity__lt=F('reorder_level')
                    ).count()
                    context['recent_dispensations'] = Prescription.objects.filter(
                        dispensed_by=user # Assuming dispensed_by links to User
                    ).order_by('-dispensed_date')[:5]
                except Pharmacist.DoesNotExist:
                    context['error'] = "Pharmacist profile not found."

            elif user.user_type == 'lab_tech':
                try:
                    lab_tech = user.labtechnician # Assuming LabTechnician profile
                    context['pending_lab_requests'] = LabTestRequest.objects.filter(
                        status='pending' # Or similar status indicating ready for tech
                    ).count()
                    context['recent_lab_results'] = LabTestResult.objects.filter(
                        performed_by=user # Assuming performed_by links to User
                    ).order_by('-result_date')[:5]
                except LabTechnician.DoesNotExist:
                    context['error'] = "Lab Technician profile not found."

            elif user.user_type == 'radiologist':
                try:
                    radiologist = user.radiologist # Assuming Radiologist profile
                    context['pending_imaging_reports'] = ImagingRequest.objects.filter(
                        status='performed' # Assume 'performed' means ready for reporting
                    ).count()
                    context['recent_imaging_results'] = ImagingResult.objects.filter(
                        radiologist=user # Assuming radiologist links to User
                    ).order_by('-report_date')[:5]
                except Radiologist.DoesNotExist:
                    context['error'] = "Radiologist profile not found."

            elif user.user_type == 'receptionist':
                try:
                    receptionist = user.receptionist # Assuming Receptionist profile
                    context['today_appointments'] = Appointment.objects.filter(
                        appointment_date__gte=today_start,
                        appointment_date__lte=today_end,
                        status='scheduled'
                    ).count()
                    context['new_patient_registrations_today'] = Patient.objects.filter(
                        registration_date__gte=today_start,
                        registration_date__lte=today_end
                    ).count()
                    context['recent_appointments_reception'] = Appointment.objects.filter(
                        appointment_date__gte=current_datetime - timedelta(days=7) # Last 7 days
                    ).order_by('-appointment_date')[:5]
                except Receptionist.DoesNotExist:
                    context['error'] = "Receptionist profile not found."

            elif user.user_type == 'nurse':
                try:
                    nurse = user.nurse
                    context['assigned_beds'] = Bed.objects.filter(assigned_nurse=nurse, is_occupied=True).count()
                    context['recent_patient_vitals'] = VitalSign.objects.filter(recorded_by=user).order_by('-timestamp')[:5]
                    context['recent_encounters_assisted'] = Encounter.objects.filter(nurse=nurse).order_by('-encounter_date')[:5]
                except Nurse.DoesNotExist:
                    context['error'] = "Nurse profile not found."

            elif user.user_type == 'procurement_officer':
                try:
                    proc_officer = user.procurementofficer
                    context['low_stock_items_procurement'] = Medication.objects.filter(
                        stock_quantity__lt=F('reorder_level')
                    ).count()
                    context['recent_purchase_orders'] = [] # Placeholder for future PO model
                    # You'd typically filter by a `created_by` or `responsible_officer` field on a PurchaseOrder model
                except ProcurementOfficer.DoesNotExist:
                    context['error'] = "Procurement Officer profile not found."


        return context

def select_user_type(request):
    user_types = [
        {'name': 'Patient', 'url_name': 'register_by_type', 'type_slug': 'patient', 'icon': 'fas fa-hospital-user'},
        {'name': 'Doctor', 'url_name': 'register_by_type', 'type_slug': 'doctor', 'icon': 'fas fa-user-md'},
        {'name': 'Nurse', 'url_name': 'register_by_type', 'type_slug': 'nurse', 'icon': 'fas fa-user-nurse'},
        {'name': 'Pharmacist', 'url_name': 'register_by_type', 'type_slug': 'pharmacist', 'icon': 'fas fa-prescription-bottle-alt'},
        {'name': 'Procurement Officer', 'url_name': 'register_by_type', 'type_slug': 'procurement_officer', 'icon': 'fas fa-truck-loading'},
        {'name': 'Admin Staff', 'url_name': 'register_by_type', 'type_slug': 'admin', 'icon': 'fas fa-user-shield'},
        {'name': 'Receptionist', 'url_name': 'register_by_type', 'type_slug': 'receptionist', 'icon': 'fas fa-concierge-bell'},
        {'name': 'Lab Technician', 'url_name': 'register_by_type', 'type_slug': 'lab_tech', 'icon': 'fas fa-flask'},
        {'name': 'Radiologist', 'url_name': 'register_by_type', 'type_slug': 'radiologist', 'icon': 'fas fa-x-ray'},
    ]
    context = {'user_types': user_types}
    return render(request, 'clinical_app/user_management/select_user_type.html', context)

# --- GENERAL USER REGISTRATION VIEW ---
USER_TYPE_PREFIXES = {
    'patient': 'PT',
    'doctor': 'DR',
    'nurse': 'NS',
    'pharmacist': 'PH',
    'lab_tech': 'LT',
    'radiologist': 'RD',
    'receptionist': 'RC',
    'procurement_officer': 'PO',
    'admin': 'AD', # For admin users
    # Add other user types as needed
}

class UserRegistrationView(CreateView):
    template_name = 'clinical_app/user_management/register.html'
    success_url = reverse_lazy('login') # User needs to log in with new credentials

    def get_form_class(self):
        """
        Dynamically returns the appropriate form class based on the 'user_type'
        URL parameter. Ensures all registration forms use the CustomUserCreationForm
        as their base to handle password auto-generation and hiding.
        """
        user_type = self.kwargs.get('user_type', None)

        if user_type == 'patient':
            return PatientRegistrationForm
        elif user_type == 'doctor':
            return DoctorRegistrationForm
        elif user_type == 'nurse':
            return NurseRegistrationForm
        elif user_type == 'pharmacist':
            return PharmacistRegistrationForm
        elif user_type == 'procurement_officer':
            return ProcurementOfficerRegistrationForm
        elif user_type == 'receptionist':
            return ReceptionistRegistrationForm
        elif user_type == 'lab_tech':
            return LabTechnicianRegistrationForm
        elif user_type == 'radiologist':
            return RadiologistRegistrationForm
        elif user_type == 'admin':
            # This is typically for superusers or staff, might not have a specific profile model
            return CustomUserCreationForm
        else:
            messages.error(self.request, "Invalid or unsupported user type for registration. Please choose a valid type.")
            # Fallback to CustomUserCreationForm for general or unrecognized types
            return CustomUserCreationForm 

    def get_form_kwargs(self):
        """
        Passes the 'user_type' from URL kwargs to the form's __init__ method.
        This is crucial if your forms use 'user_type' to dynamically add/remove fields
        or set placeholders/initial data, although for password handling, the inheritance
        from CustomUserCreationForm is the primary mechanism.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user_type'] = self.kwargs.get('user_type', None)
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Adds user_type and a display-friendly version to the template context.
        """
        context = super().get_context_data(**kwargs)
        user_type = self.kwargs.get('user_type', 'general')
        context['user_type'] = user_type
        context['display_user_type'] = user_type.replace('_', ' ').title()
        return context

    def form_valid(self, form):
        """
        Handles valid form submissions:
        1. Creates the User instance with an auto-generated username and password.
        2. Retrieves the temporary raw password for communication.
        3. Creates the specific profile (Patient, Doctor, etc.) based on user_type.
        4. Logs the activity.
        5. Sends an email with credentials (best practice).
        6. Displays a temporary message with credentials (for development only).
        """
        user_type = self.kwargs.get('user_type', 'general')
        
        # Use a transaction to ensure atomic creation of user and profile.
        # If any step fails, the entire transaction is rolled back.
        try:
            with transaction.atomic():
                # Step 1: Save the user instance.
                # The form's save method (from CustomUserCreationForm) handles:
                # - Auto-generating username based on prefix.
                # - Auto-generating a secure raw password.
                # - Hashing the password.
                # - Setting the user.user_type field.
                user = form.save(commit=True, user_type=user_type)

                # Step 2: Retrieve the raw password.
                # It's temporarily stored on the user object by CustomUserCreationForm's save method.
                raw_password = getattr(user, '_raw_password', None)
                if raw_password is None:
                    logger.error(f"form.save() for {user.username} did not set _raw_password. User creation rolled back.")
                    # Add a non-field error to the form to trigger form_invalid.
                    form.add_error(None, "An internal error occurred: password could not be generated. Please try again.")
                    return self.form_invalid(form)

                # Step 3: Create specific profile based on user type and cleaned data.
                profile_instance = None 

                if user_type == 'patient':
                    profile_instance = Patient.objects.create(
                        user=user,
                        blood_group=form.cleaned_data.get('blood_group'),
                        emergency_contact_name=form.cleaned_data.get('emergency_contact_name'),
                        emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone'),
                        allergies=form.cleaned_data.get('allergies'),
                        pre_existing_conditions=form.cleaned_data.get('pre_existing_conditions'),
                    )
                elif user_type == 'doctor':
                    # Assuming 'department' is a required field in DoctorRegistrationForm and validated there.
                    profile_instance = Doctor.objects.create(
                        user=user,
                        specialization=form.cleaned_data['specialization'],
                        medical_license_number=form.cleaned_data['medical_license_number'],
                        department=form.cleaned_data['department'], 
                        years_of_experience=form.cleaned_data.get('years_of_experience'),
                    )
                elif user_type == 'nurse':
                    profile_instance = Nurse.objects.create(
                        user=user,
                        shift_info=form.cleaned_data.get('shift_info'),
                        assigned_ward=form.cleaned_data.get('assigned_ward'),
                    )
                elif user_type == 'pharmacist':
                    profile_instance = Pharmacist.objects.create(
                        user=user,
                        pharmacy_license_number=form.cleaned_data.get('pharmacy_license_number'),
                        employee_id=form.cleaned_data.get('employee_id'),
                    )
                elif user_type == 'procurement_officer':
                    profile_instance = ProcurementOfficer.objects.create(
                        user=user,
                        employee_id=form.cleaned_data.get('employee_id'),
                        department=form.cleaned_data.get('department'),
                    )
                elif user_type == 'receptionist':
                    profile_instance = Receptionist.objects.create(
                        user=user,
                        shift_info=form.cleaned_data.get('shift_info'),
                        assigned_desk=form.cleaned_data.get('assigned_desk'),
                    )
                elif user_type == 'lab_tech':
                    profile_instance = LabTechnician.objects.create(
                        user=user,
                        license_number=form.cleaned_data.get('license_number'),
                        specialization=form.cleaned_data.get('specialization'),
                        shift_info=form.cleaned_data.get('shift_info'),
                        lab_section_assigned=form.cleaned_data.get('lab_section_assigned'),
                        qualifications=form.cleaned_data.get('qualifications'),
                        status=form.cleaned_data.get('status'),
                    )
                elif user_type == 'radiologist':
                    profile_instance = Radiologist.objects.create(
                        user=user,
                        medical_license_number=form.cleaned_data.get('medical_license_number'),
                        sub_specialization=form.cleaned_data.get('sub_specialization'),
                        date_hired=form.cleaned_data.get('date_hired'),
                        on_call_status=form.cleaned_data.get('on_call_status'),
                        preferred_modalities=form.cleaned_data.get('preferred_modalities'),
                        qualifications=form.cleaned_data.get('qualifications'),
                        status=form.cleaned_data.get('status'),
                    )
                
                # Step 4: Log successful user and profile creation.
                log_activity(
                    self.request.user if self.request.user.is_authenticated else None,
                    'CREATE',
                    f'Registered new {user_type} user: {user.get_full_name()} (Username: {user.username})',
                    model_name='User',
                    object_id=user.pk,
                    ip_address=get_client_ip(self.request)
                )
                if profile_instance:
                    log_activity(
                        self.request.user if self.request.user.is_authenticated else None,
                        'CREATE',
                        f'Created {user_type} profile for {user.username}',
                        model_name=profile_instance.__class__.__name__,
                        object_id=profile_instance.pk,
                        ip_address=get_client_ip(self.request)
                    )

                # Step 5: Send email with credentials.
                # This is the most secure way to provide credentials.
                try:
                    subject = f"Your New {user_type.replace('_', ' ').title()} Account at {getattr(settings, 'HOSPITAL_NAME', 'Our Hospital')}"
                    html_message = render_to_string('clinical_app/emails/new_user_credentials.html', {
                        'user': user,
                        'username': user.username,
                        'password': raw_password, 
                        'login_url': self.request.build_absolute_uri(reverse_lazy('login')),
                        'hospital_name': getattr(settings, 'HOSPITAL_NAME', 'Our Hospital')
                    })
                    plain_message = strip_tags(html_message)
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')
                    to_email = user.email

                    send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
                    messages.success(self.request, f"{user_type.replace('_', ' ').title()} registered successfully! Credentials sent to {user.email}.")
                except Exception as e:
                    messages.warning(self.request, f"User registered, but failed to send credentials email to {user.email}. Please notify them manually. Error: {e}")
                    logger.error(f"Failed to send email to {user.email} for new {user_type} user {user.username}: {e}", exc_info=True)

                # Step 6: Display temporary password (for development/testing ONLY).
                # REMOVE this in a production environment for security!
                messages.info(self.request,
                              f"New User: <strong>{user.username}</strong>, Temporary Password: <strong><span class='text-danger'>{raw_password}</span></strong>. "
                              f"Please ensure the user logs in and changes their password immediately. "
                              f"This message is for development purposes and will be removed in production.")

        except ValidationError as e:
            # Catch ValidationErrors explicitly raised within the atomic block for a cleaner message.
            messages.error(self.request, f"Registration failed: {e.message}")
            return self.form_invalid(form)
        except Exception as e:
            # Catch any other unexpected errors during the transaction.
            logger.exception(f"An unexpected error occurred during {user_type} user registration for {form.cleaned_data.get('email')}: {e}")
            messages.error(self.request, "An unexpected error occurred during registration. Please contact support.")
            return self.form_invalid(form)

        # If everything within the atomic block succeeded without raising an exception,
        # proceed to the success_url.
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handles invalid form submissions by adding a general error message
        and re-rendering the form with specific field errors.
        """
        messages.error(self.request, "Please correct the errors below to register the account.")
        return super().form_invalid(form)

class ConsentFormCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = ConsentForm
    form_class = ConsentFormForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('patient_detail', kwargs={'pk': self.kwargs['patient_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient'] = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        context['form_title'] = "Add Consent Form"
        return context

    def form_valid(self, form):
        form.instance.patient = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        form.instance.signed_by_staff = self.request.user
        return super().form_valid(form)

class PatientListView(LoginRequiredMixin, IsMedicalStaffMixin, ListView):
    model = Patient
    template_name = 'clinical_app/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 10
    ordering = ['user__last_name', 'user__first_name']

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(patient_id__icontains=query) |
                Q(user__username__icontains=query)
            )
        return queryset

class PatientDetailView(LoginRequiredMixin, IsMedicalStaffMixin, DetailView):
    model = Patient
    template_name = 'clinical_app/patient_detail.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.get_object()
        context['encounters'] = patient.encounters.all().order_by('-encounter_date')
        context['vitals'] = VitalSign.objects.filter(encounter__patient=patient).order_by('-timestamp')[:5] # Last 5 vitals
        context['diagnoses'] = Diagnosis.objects.filter(encounter__patient=patient).order_by('-diagnosis_date')[:5]
        context['prescriptions'] = Prescription.objects.filter(encounter__patient=patient).order_by('-prescription_date')[:5]
        context['consent_forms'] = patient.consent_forms.all()

        # Log patient viewing
        log_activity(
            self.request.user,
            'VIEW',
            f'Viewed patient record: {patient.user.get_full_name()} (ID: {patient.pk})',
            model_name='Patient',
            object_id=patient.pk,
            ip_address=get_client_ip(self.request)
        )
        return context

class PatientCreateView(LoginRequiredMixin, IsAdminMixin, CreateView):
    model = Patient
    form_class = PatientRegistrationForm # This form already contains all necessary fields
    template_name = 'clinical_app/patient_form.html'
    success_url = reverse_lazy('patient_list')

    # No need to override get_context_data to add 'user_form'
    # No need to create two form instances in post()

    def form_valid(self, form):
        # The 'form' argument here is an instance of PatientRegistrationForm
        with transaction.atomic():
            user = form.save(commit=False) # This saves the User part of PatientRegistrationForm
            user.user_type = 'patient'
            user.save()

            # The Patient-specific fields are directly on the 'form'
            patient_profile = Patient.objects.create(
                user=user,
                blood_group=form.cleaned_data.get('blood_group'),
                emergency_contact_name=form.cleaned_data.get('emergency_contact_name'),
                emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone'),
                allergies=form.cleaned_data.get('allergies'),
                pre_existing_conditions=form.cleaned_data.get('pre_existing_conditions'),
            )

            log_activity(
                self.request.user,
                'CREATE',
                f'Admin created new patient: {user.get_full_name()} (ID: {patient_profile.pk})',
                model_name='Patient',
                object_id=patient_profile.pk,
                ip_address=get_client_ip(self.request)
            )
            messages.success(self.request, f"Patient {user.get_full_name()} created successfully.")
            return super().form_valid(form) # This will redirect to success_url

    def form_invalid(self, form):
        messages.error(self.request, "Error creating patient. Please correct the errors below.")
        # When form is invalid, CreateView's default behavior is to re-render the template
        # with the invalid form, which is exactly what we want.
        # We also need to define 'user_form_fields' for the template
        user_form_fields = [
            'username', 'first_name', 'last_name', 'email', 'phone_number',
            'address', 'date_of_birth', 'gender', 'password', 'password2'
        ]
        context = self.get_context_data() # Gets default context from CreateView
        context['user_form_fields'] = user_form_fields
        return self.render_to_response(context)

class PatientUpdateView(LoginRequiredMixin, IsAdminMixin, UpdateView):
    model = Patient
    form_class = PatientRegistrationForm
    template_name = 'clinical_app/patient_form.html'
    context_object_name = 'patient'

    def get_object(self, queryset=None):
        return get_object_or_404(Patient, pk=self.kwargs['pk'])

    def get_success_url(self):
        return reverse_lazy('patient_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_user = self.get_object().user
        context['user_form'] = CustomUserChangeForm(instance=patient_user, prefix='user')
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        patient_form = PatientRegistrationForm(request.POST, instance=self.object)
        user_form = CustomUserChangeForm(request.POST, instance=self.object.user, prefix='user')

        if patient_form.is_valid() and user_form.is_valid():
            with transaction.atomic():
                # Capture old data before saving
                old_patient_data = {field.name: getattr(self.object, field.name) for field in self.object._meta.fields}
                old_user_data = {field.name: getattr(self.object.user, field.name) for field in self.object.user._meta.fields}

                user = user_form.save()
                patient = patient_form.save()

                # Compare old and new data to find specific changes
                detected_changes = {}
                for field, old_value in old_patient_data.items():
                    new_value = getattr(patient, field)
                    if str(old_value) != str(new_value):
                        detected_changes[f'patient_{field}'] = {'old': str(old_value), 'new': str(new_value)}

                for field, old_value in old_user_data.items():
                    new_value = getattr(user, field)
                    if str(old_value) != str(new_value):
                        detected_changes[f'user_{field}'] = {'old': str(old_value), 'new': str(new_value)}

                log_activity(
                    request.user,
                    'UPDATE',
                    f'Updated patient record and/or user details for {patient.user.get_full_name()} (ID: {patient.pk})',
                    model_name='Patient',
                    object_id=patient.pk,
                    ip_address=get_client_ip(request),
                    changes=detected_changes if detected_changes else None
                )
            messages.success(request, f"Patient {patient.user.get_full_name()} updated successfully.")
            return redirect(self.get_success_url())
        else:
            messages.error(request, "Error updating patient. Please correct the errors.")
            context = self.get_context_data()
            context['form'] = patient_form
            context['user_form'] = user_form
            return render(request, self.template_name, context)


# --- Encounter Views (for Doctors/Nurses) ---

class EncounterDetailView(LoginRequiredMixin, IsMedicalStaffMixin, DetailView):
    model = Encounter
    template_name = 'clinical_app/encounter_detail.html'
    context_object_name = 'encounter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encounter = self.get_object()
        context['vitals'] = VitalSign.objects.filter(encounter=encounter).order_by('-timestamp')
        context['medical_history'] = MedicalHistory.objects.filter(patient=encounter.patient).order_by('-recorded_date')
        context['physical_examinations'] = PhysicalExamination.objects.filter(encounter=encounter).order_by('-examination_date')
        context['diagnoses'] = Diagnosis.objects.filter(encounter=encounter).order_by('-diagnosis_date')
        context['treatment_plans'] = TreatmentPlan.objects.filter(encounter=encounter).order_by('-created_date')
        context['lab_requests'] = LabTestRequest.objects.filter(encounter=encounter).order_by('-requested_date')
        context['imaging_requests'] = ImagingRequest.objects.filter(encounter=encounter).order_by('-requested_date')
        context['prescriptions'] = Prescription.objects.filter(encounter=encounter).order_by('-prescription_date')
        context['case_summary'] = CaseSummary.objects.filter(encounter=encounter).first()

        log_activity(
            self.request.user,
            'VIEW',
            f'Viewed encounter details for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='Encounter',
            object_id=encounter.pk,
            ip_address=get_client_ip(self.request)
        )
        return context

class EncounterCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = Encounter
    fields = ['patient', 'doctor', 'appointment', 'encounter_type', 'admission_date', 'discharge_date', 'ward', 'bed']
    template_name = 'clinical_app/encounter_form.html'
    success_url = reverse_lazy('home')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.fields['doctor'].initial = self.request.user.doctor
            form.fields['doctor'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        if not form.cleaned_data.get('doctor') and self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.instance.doctor = self.request.user.doctor

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Created new encounter for patient {form.instance.patient.user.get_full_name()} (Encounter ID: {form.instance.pk})',
            model_name='Encounter',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, f"Encounter for {form.instance.patient.user.get_full_name()} created successfully.")
        return response

# --- Sub-form Views (e.g., adding vitals to an encounter) ---

class VitalSignCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = VitalSign
    form_class = VitalSignForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Record Vital Signs"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.recorded_by = self.request.user

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Recorded vital signs for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='VitalSign',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Vital signs recorded successfully.")
        return response

class PatientListView(LoginRequiredMixin, IsMedicalStaffMixin, ListView):
    model = Patient
    template_name = 'clinical_app/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 10
    ordering = ['user__last_name', 'user__first_name']

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(patient_id__icontains=query) |
                Q(user__username__icontains=query)
            )
        return queryset

class PatientDetailView(LoginRequiredMixin, IsMedicalStaffMixin, DetailView):
    model = Patient
    template_name = 'clinical_app/patient_detail.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.get_object()
        context['encounters'] = patient.encounters.all().order_by('-encounter_date')
        context['vitals'] = VitalSign.objects.filter(encounter__patient=patient).order_by('-timestamp')[:5] # Last 5 vitals
        context['diagnoses'] = Diagnosis.objects.filter(encounter__patient=patient).order_by('-diagnosis_date')[:5]
        context['prescriptions'] = Prescription.objects.filter(encounter__patient=patient).order_by('-prescription_date')[:5]
        context['consent_forms'] = patient.consent_forms.all()

        # Log patient viewing
        log_activity(
            self.request.user,
            'VIEW',
            f'Viewed patient record: {patient.user.get_full_name()} (ID: {patient.pk})',
            model_name='Patient',
            object_id=patient.pk,
            ip_address=get_client_ip(self.request)
        )
        return context

class DoctorPatientListView(LoginRequiredMixin, IsDoctorMixin, ListView):
    model = Patient
    template_name = 'clinical_app/doctor_patient_list.html'
    context_object_name = 'patients' # This will now be a list of dicts, not just Patient objects
    paginate_by = 10

    def get_queryset(self):
        # Ensure the doctor profile exists for the current user
        doctor_profile = get_object_or_404(Doctor, user=self.request.user)

        # Get patients associated with this doctor through encounters
        # Use .distinct() to avoid duplicate patients if they have multiple encounters
        queryset = Patient.objects.filter(encounters__doctor=doctor_profile).distinct()

        # Apply search query if present
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(patient_id__icontains=query) # Assuming Patient model has patient_id
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor_profile = get_object_or_404(Doctor, user=self.request.user)

        # Get the paginated patients (objects in the current page)
        patients_on_page = context['patients'] # 'patients' refers to the paginated queryset

        # Build a list of patient data, including their latest encounter
        patients_with_latest_encounter = []
        for patient in patients_on_page:
            # Fetch the latest encounter for this patient by the current doctor
            latest_encounter = patient.encounters.filter(doctor=doctor_profile).order_by('-encounter_date').first()
            patients_with_latest_encounter.append({
                'patient': patient,
                'latest_encounter': latest_encounter
            })

        # Override the 'patients' context variable with our new list
        context['patients'] = patients_with_latest_encounter
        return context

# --- Encounter Views (for Doctors/Nurses) ---

class EncounterDetailView(LoginRequiredMixin, IsMedicalStaffMixin, DetailView):
    model = Encounter
    template_name = 'clinical_app/encounter_detail.html'
    context_object_name = 'encounter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encounter = self.get_object()
        context['vitals'] = VitalSign.objects.filter(encounter=encounter).order_by('-timestamp')
        context['medical_history'] = MedicalHistory.objects.filter(patient=encounter.patient).order_by('-recorded_date')
        context['physical_examinations'] = PhysicalExamination.objects.filter(encounter=encounter).order_by('-examination_date')
        context['diagnoses'] = Diagnosis.objects.filter(encounter=encounter).order_by('-diagnosis_date')
        context['treatment_plans'] = TreatmentPlan.objects.filter(encounter=encounter).order_by('-created_date')
        context['lab_requests'] = LabTestRequest.objects.filter(encounter=encounter).order_by('-requested_date')
        context['imaging_requests'] = ImagingRequest.objects.filter(encounter=encounter).order_by('-requested_date')
        context['prescriptions'] = Prescription.objects.filter(encounter=encounter).order_by('-prescription_date')
        context['case_summary'] = CaseSummary.objects.filter(encounter=encounter).first()

        log_activity(
            self.request.user,
            'VIEW',
            f'Viewed encounter details for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='Encounter',
            object_id=encounter.pk,
            ip_address=get_client_ip(self.request)
        )
        return context

class EncounterCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = Encounter
    fields = ['patient', 'doctor', 'appointment', 'encounter_type', 'admission_date', 'discharge_date', 'ward', 'bed']
    template_name = 'clinical_app/encounter_form.html'
    success_url = reverse_lazy('home')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Prefill doctor if current user is a doctor
        if self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.fields['doctor'].initial = self.request.user.doctor
            form.fields['doctor'].widget = forms.HiddenInput() # Hide the field

        # Filter patients to only show active ones, if applicable
        # form.fields['patient'].queryset = Patient.objects.filter(is_active=True)

        # Filter doctors to only show active ones
        form.fields['doctor'].queryset = Doctor.objects.filter(user__is_active=True)

        # Filter wards and beds
        form.fields['ward'].queryset = Ward.objects.all()
        # Initializing bed choices based on selected ward (might need JS for dynamic update)
        if 'ward' in self.request.POST:
            try:
                ward_id = int(self.request.POST.get('ward'))
                form.fields['bed'].queryset = Bed.objects.filter(ward_id=ward_id, is_occupied=False)
            except (ValueError, TypeError):
                form.fields['bed'].queryset = Bed.objects.none()
        elif self.instance.pk: # For update view if instance exists
            form.fields['bed'].queryset = Bed.objects.filter(Q(ward=self.instance.ward) | Q(is_occupied=False))
        else:
            form.fields['bed'].queryset = Bed.objects.none() # No ward selected initially

        return form

    def form_valid(self, form):
        if not form.cleaned_data.get('doctor') and self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.instance.doctor = self.request.user.doctor

        with transaction.atomic():
            response = super().form_valid(form) # Save the form and get the instance

            # If a bed was assigned, mark it as occupied
            if form.instance.bed:
                bed = form.instance.bed
                if not bed.is_occupied:
                    bed.is_occupied = True
                    bed.save()
                    log_activity(
                        self.request.user,
                        'UPDATE',
                        f'Bed {bed.bed_number} in {bed.ward.name} marked as occupied due to encounter {form.instance.pk}',
                        model_name='Bed',
                        object_id=bed.pk,
                        ip_address=get_client_ip(self.request),
                        changes={'is_occupied': {'old': False, 'new': True}}
                    )

            log_activity(
                self.request.user,
                'CREATE',
                f'Created new encounter for patient {form.instance.patient.user.get_full_name()} (Encounter ID: {form.instance.pk})',
                model_name='Encounter',
                object_id=form.instance.pk,
                ip_address=get_client_ip(self.request)
            )
        messages.success(self.request, f"Encounter for {form.instance.patient.user.get_full_name()} created successfully.")
        return response

class EncounterUpdateView(LoginRequiredMixin, IsMedicalStaffMixin, UpdateView): # Added Update View for Encounter
    model = Encounter
    fields = ['patient', 'doctor', 'appointment', 'encounter_type', 'admission_date', 'discharge_date', 'ward', 'bed']
    template_name = 'clinical_app/encounter_form.html'
    context_object_name = 'encounter'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Prefill doctor if current user is a doctor and the field is not already set
        if self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor') and not form.instance.doctor:
            form.fields['doctor'].initial = self.request.user.doctor
            form.fields['doctor'].widget = forms.HiddenInput() # Hide the field

        # Filter doctors to only show active ones
        form.fields['doctor'].queryset = Doctor.objects.filter(user__is_active=True)

        # Filter wards and beds
        form.fields['ward'].queryset = Ward.objects.all()
        # Initialize bed choices dynamically
        if self.request.method == 'GET' and self.object.ward:
            form.fields['bed'].queryset = Bed.objects.filter(Q(ward=self.object.ward) | Q(is_occupied=False))
        elif 'ward' in self.request.POST:
            try:
                ward_id = int(self.request.POST.get('ward'))
                form.fields['bed'].queryset = Bed.objects.filter(ward_id=ward_id, is_occupied=False)
            except (ValueError, TypeError):
                form.fields['bed'].queryset = Bed.objects.none()
        else:
            form.fields['bed'].queryset = Bed.objects.all() # Or restrict as needed

        return form

    def form_valid(self, form):
        with transaction.atomic():
            old_encounter = Encounter.objects.get(pk=self.object.pk) # Get the old instance before saving
            old_bed = old_encounter.bed

            response = super().form_valid(form) # Save the form and get the updated instance
            updated_encounter = self.object # The updated instance

            # Handle bed changes
            new_bed = updated_encounter.bed
            if old_bed != new_bed:
                # If old_bed existed and is different from new_bed, unoccupy the old bed
                if old_bed and old_bed.is_occupied:
                    old_bed.is_occupied = False
                    old_bed.save()
                    log_activity(
                        self.request.user,
                        'UPDATE',
                        f'Bed {old_bed.bed_number} in {old_bed.ward.name} un-occupied from encounter {updated_encounter.pk}',
                        model_name='Bed',
                        object_id=old_bed.pk,
                        ip_address=get_client_ip(self.request),
                        changes={'is_occupied': {'old': True, 'new': False}}
                    )
                # If a new_bed is assigned and not occupied, occupy it
                if new_bed and not new_bed.is_occupied:
                    new_bed.is_occupied = True
                    new_bed.save()
                    log_activity(
                        self.request.user,
                        'UPDATE',
                        f'Bed {new_bed.bed_number} in {new_bed.ward.name} occupied for encounter {updated_encounter.pk}',
                        model_name='Bed',
                        object_id=new_bed.pk,
                        ip_address=get_client_ip(self.request),
                        changes={'is_occupied': {'old': False, 'new': True}}
                    )

            # Capture changes for activity log
            detected_changes = {}
            for field in form.changed_data:
                old_value = form.initial.get(field)
                new_value = form.cleaned_data.get(field)
                if str(old_value) != str(new_value):
                    detected_changes[field] = {'old': str(old_value), 'new': str(new_value)}


            log_activity(
                self.request.user,
                'UPDATE',
                f'Updated encounter for patient {updated_encounter.patient.user.get_full_name()} (Encounter ID: {updated_encounter.pk})',
                model_name='Encounter',
                object_id=updated_encounter.pk,
                ip_address=get_client_ip(self.request),
                changes=detected_changes if detected_changes else None
            )
        messages.success(self.request, f"Encounter for {updated_encounter.patient.user.get_full_name()} updated successfully.")
        return response

class EncounterDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView): # Added Delete View for Encounter
    model = Encounter
    template_name = 'clinical_app/confirm_delete.html'
    success_url = reverse_lazy('patient_list') # Redirect to patient list after deletion
    context_object_name = 'object'

    def form_valid(self, form):
        encounter = self.get_object()
        patient_name = encounter.patient.user.get_full_name()
        encounter_id = encounter.pk

        with transaction.atomic():
            # If the encounter had an associated bed, unoccupy it
            if encounter.bed and encounter.bed.is_occupied:
                bed = encounter.bed
                bed.is_occupied = False
                bed.save()
                log_activity(
                    self.request.user,
                    'UPDATE',
                    f'Bed {bed.bed_number} in {bed.ward.name} un-occupied due to deletion of encounter {encounter_id}',
                    model_name='Bed',
                    object_id=bed.pk,
                    ip_address=get_client_ip(self.request),
                    changes={'is_occupied': {'old': True, 'new': False}}
                )

            response = super().form_valid(form) # Perform the deletion

            log_activity(
                self.request.user,
                'DELETE',
                f'Deleted encounter for patient {patient_name} (Encounter ID: {encounter_id})',
                model_name='Encounter',
                object_id=encounter_id,
                ip_address=get_client_ip(self.request)
            )
        messages.success(self.request, f"Encounter for {patient_name} deleted successfully.")
        return response

# --- Sub-form Views (e.g., adding vitals to an encounter) ---

class VitalSignCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = VitalSign
    form_class = VitalSignForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Record Vital Signs"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.recorded_by = self.request.user

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Recorded vital signs for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='VitalSign',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Vital signs recorded successfully.")
        return response

class MedicalHistoryCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = MedicalHistory
    form_class = MedicalHistoryForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('patient_detail', kwargs={'pk': self.kwargs['patient_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient'] = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        context['form_title'] = "Add Medical History"
        return context

    def form_valid(self, form):
        patient = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        form.instance.patient = patient
        form.instance.recorded_by = self.request.user.doctor # Assuming a direct link

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Added medical history for patient {patient.user.get_full_name()} (Medical History ID: {form.instance.pk})',
            model_name='MedicalHistory',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Medical history added successfully.")
        return response

class PhysicalExaminationCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = PhysicalExamination
    form_class = PhysicalExaminationForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Record Physical Examination"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.examined_by = self.request.user.doctor

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Recorded physical examination for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='PhysicalExamination',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Physical examination recorded successfully.")
        return response

class DiagnosisCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = Diagnosis
    form_class = DiagnosisForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Add Diagnosis"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.diagnosed_by = self.request.user.doctor

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Added diagnosis for patient {encounter.patient.user.get_full_name()} (Diagnosis ID: {form.instance.pk})',
            model_name='Diagnosis',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Diagnosis added successfully.")
        return response

class TreatmentPlanCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = TreatmentPlan
    form_class = TreatmentPlanForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Create Treatment Plan"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.created_by = self.request.user.doctor

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Created treatment plan for patient {encounter.patient.user.get_full_name()} (Treatment Plan ID: {form.instance.pk})',
            model_name='TreatmentPlan',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Treatment plan created successfully.")
        return response

class LabTestRequestCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = LabTestRequest
    form_class = LabTestRequestForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Request Lab Tests"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.requested_by = self.request.user.doctor

        response = super().form_valid(form) # Save the form and get the instance

        log_activity(
            self.request.user,
            'CREATE',
            f'Requested lab test for patient {encounter.patient.user.get_full_name()} (Request ID: {form.instance.pk}, Tests: {form.instance.get_tests_display()})',
            model_name='LabTestRequest',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Lab test request submitted successfully.")
        return response

class LabTestResultCreateView(LoginRequiredMixin, IsLabTechMixin, CreateView): # Changed to IsLabTechMixin
    model = LabTestResult
    form_class = LabTestResultForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        lab_request_pk = self.kwargs.get('lab_request_pk')
        if lab_request_pk:
            lab_request = get_object_or_404(LabTestRequest, pk=lab_request_pk)
            return reverse_lazy('encounter_detail', kwargs={'pk': lab_request.encounter.pk})
        return reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lab_request'] = get_object_or_404(LabTestRequest, pk=self.kwargs['lab_request_pk'])
        context['form_title'] = f"Record Result for {context['lab_request'].get_tests_display()}"
        return context

    def form_valid(self, form):
        lab_request = get_object_or_404(LabTestRequest, pk=self.kwargs['lab_request_pk'])
        form.instance.request = lab_request
        form.instance.performed_by = self.request.user # Assuming LabTech user profile is linked to User

        with transaction.atomic():
            response = super().form_valid(form) # Save the form and get the instance

            # Update the status of the LabTestRequest
            if lab_request.status != 'completed':
                lab_request.status = 'completed'
                lab_request.save()
                log_activity(
                    self.request.user,
                    'UPDATE',
                    f'Lab test request status updated to completed for {lab_request.patient.user.get_full_name()} (Request ID: {lab_request.pk})',
                    model_name='LabTestRequest',
                    object_id=lab_request.pk,
                    ip_address=get_client_ip(self.request),
                    changes={'status': {'old': lab_request.status, 'new': 'completed'}} # Old status might be different, but logging the change
                )

            log_activity(
                self.request.user,
                'CREATE',
                f'Recorded lab test result for patient {lab_request.patient.user.get_full_name()} (Request ID: {lab_request.pk}, Result ID: {form.instance.pk})',
                model_name='LabTestResult',
                object_id=form.instance.pk,
                ip_address=get_client_ip(self.request)
            )
        messages.success(self.request, "Lab test result recorded successfully and request marked as complete.")
        return response

class ImagingRequestCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView): # Added ImagingRequestCreateView
    model = ImagingRequest
    form_class = ImagingRequestForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Request Imaging"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.requested_by = self.request.user.doctor

        response = super().form_valid(form)

        log_activity(
            self.request.user,
            'CREATE',
            f'Requested imaging for patient {encounter.patient.user.get_full_name()} (Request ID: {form.instance.pk}, Type: {form.instance.imaging_type.name})',
            model_name='ImagingRequest',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Imaging request submitted successfully.")
        return response

class ImagingResultCreateView(LoginRequiredMixin, IsRadiologistMixin, CreateView): # Changed to IsRadiologistMixin
    model = ImagingResult
    form_class = ImagingResultForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        imaging_request_pk = self.kwargs.get('imaging_request_pk')
        if imaging_request_pk:
            imaging_request = get_object_or_404(ImagingRequest, pk=imaging_request_pk)
            return reverse_lazy('encounter_detail', kwargs={'pk': imaging_request.encounter.pk})
        return reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['imaging_request'] = get_object_or_404(ImagingRequest, pk=self.kwargs['imaging_request_pk'])
        context['form_title'] = f"Record Result for {context['imaging_request'].imaging_type.name}"
        return context

    def form_valid(self, form):
        imaging_request = get_object_or_404(ImagingRequest, pk=self.kwargs['imaging_request_pk'])
        form.instance.request = imaging_request
        form.instance.radiologist = self.request.user # Assuming Radiologist user profile is linked to User

        with transaction.atomic():
            response = super().form_valid(form)

            # Update the status of the ImagingRequest
            if imaging_request.status != 'completed':
                imaging_request.status = 'completed'
                imaging_request.save()
                log_activity(
                    self.request.user,
                    'UPDATE',
                    f'Imaging request status updated to completed for {imaging_request.patient.user.get_full_name()} (Request ID: {imaging_request.pk})',
                    model_name='ImagingRequest',
                    object_id=imaging_request.pk,
                    ip_address=get_client_ip(self.request),
                    changes={'status': {'old': imaging_request.status, 'new': 'completed'}}
                )

            log_activity(
                self.request.user,
                'CREATE',
                f'Recorded imaging result for patient {imaging_request.patient.user.get_full_name()} (Request ID: {imaging_request.pk}, Result ID: {form.instance.pk})',
                model_name='ImagingResult',
                object_id=form.instance.pk,
                ip_address=get_client_ip(self.request)
            )
        messages.success(self.request, "Imaging result recorded successfully and request marked as complete.")
        return response

class PrescriptionCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView): # Added PrescriptionCreateView
    model = Prescription
    form_class = PrescriptionForm
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Prescribe Medication"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        form.instance.encounter = encounter
        form.instance.prescribed_by = self.request.user.doctor
        form.instance.patient = encounter.patient # Assign patient from encounter

        response = super().form_valid(form)

        log_activity(
            self.request.user,
            'CREATE',
            f'Prescribed medication for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk}, Prescription ID: {form.instance.pk})',
            model_name='Prescription',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Prescription created successfully.")
        return response

class PrescriptionDispenseView(LoginRequiredMixin, IsPharmacistMixin, UpdateView): # Added Dispense View
    model = Prescription
    fields = ['is_dispensed', 'dispensed_date', 'dispensed_by'] # Only allow these fields for dispense
    template_name = 'clinical_app/prescription_dispense_form.html'
    context_object_name = 'prescription'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_dispensed:
            messages.info(self.request, "This prescription has already been dispensed.")
            return redirect(reverse_lazy('encounter_detail', kwargs={'pk': obj.encounter.pk}))
        return obj

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['dispensed_by'].initial = self.request.user
        form.fields['dispensed_by'].widget = forms.HiddenInput()
        form.fields['dispensed_date'].initial = timezone.now().date() # Pre-fill with current date
        form.fields['dispensed_date'].widget = forms.HiddenInput() # Hide as it's pre-filled
        return form

    def form_valid(self, form):
        with transaction.atomic():
            prescription = form.instance
            if not prescription.is_dispensed: # Only proceed if not already dispensed
                prescription.is_dispensed = True
                prescription.dispensed_date = timezone.now().date()
                prescription.dispensed_by = self.request.user

                # Decrease medication stock (assuming Medication model has stock_quantity)
                # This logic assumes a direct link between Prescription and Medication, adjust if needed
                if prescription.medication and prescription.medication.stock_quantity >= prescription.dosage: # Assuming dosage is the quantity
                    prescription.medication.stock_quantity -= prescription.dosage
                    prescription.medication.save()
                    log_activity(
                        self.request.user,
                        'UPDATE',
                        f'Decreased stock for {prescription.medication.name} by {prescription.dosage} (New stock: {prescription.medication.stock_quantity})',
                        model_name='Medication',
                        object_id=prescription.medication.pk,
                        ip_address=get_client_ip(self.request),
                        changes={'stock_quantity': {'old': prescription.medication.stock_quantity + prescription.dosage, 'new': prescription.medication.stock_quantity}}
                    )
                else:
                    messages.error(self.request, f"Insufficient stock for {prescription.medication.name}.")
                    return self.form_invalid(form) # Or redirect with an error message

                response = super().form_valid(form)

                log_activity(
                    self.request.user,
                    'DISPENSE',
                    f'Dispensed prescription {prescription.pk} for {prescription.patient.user.get_full_name()}',
                    model_name='Prescription',
                    object_id=prescription.pk,
                    ip_address=get_client_ip(self.request),
                    changes={'is_dispensed': {'old': False, 'new': True}}
                )
                messages.success(self.request, "Prescription successfully dispensed and stock updated.")
                return response
            else:
                messages.info(self.request, "This prescription was already dispensed.")
                return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.object.encounter.pk})


class CaseSummaryCreateView(LoginRequiredMixin, IsDoctorMixin, CreateView):
    model = CaseSummary
    fields = ['summary_text']
    template_name = 'clinical_app/sub_form.html'

    def get_success_url(self):
        return reverse_lazy('encounter_detail', kwargs={'pk': self.kwargs['encounter_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        context['form_title'] = "Add Case Summary"
        # Pre-populate if a summary already exists
        existing_summary = CaseSummary.objects.filter(encounter=context['encounter']).first()
        if existing_summary:
            context['form'] = self.form_class(instance=existing_summary)
            context['form_title'] = "Edit Case Summary"
        return context

    def form_valid(self, form):
        encounter = get_object_or_404(Encounter, pk=self.kwargs['encounter_pk'])
        # Check if a summary already exists for this encounter
        existing_summary = CaseSummary.objects.filter(encounter=encounter).first()

        if existing_summary:
            # Update existing summary
            form_instance = form.save(commit=False)
            form_instance.pk = existing_summary.pk # Ensure it updates the existing one
            form_instance.encounter = encounter
            form_instance.created_by = self.request.user.doctor
            form_instance.save(update_fields=['summary_text', 'created_by', 'created_date']) # Explicitly update fields
            log_action = 'UPDATE'
            log_description = f'Updated case summary for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})'
            object_pk = existing_summary.pk
        else:
            # Create new summary
            form.instance.encounter = encounter
            form.instance.created_by = self.request.user.doctor
            form_instance = form.save()
            log_action = 'CREATE'
            log_description = f'Created case summary for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})'
            object_pk = form_instance.pk

        log_activity(
            self.request.user,
            log_action,
            log_description,
            model_name='CaseSummary',
            object_id=object_pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Case summary saved successfully.")
        return redirect(self.get_success_url())

# --- Appointment Views ---

class AppointmentListView(LoginRequiredMixin, ListView):
    model = Appointment
    template_name = 'clinical_app/appointment_list.html'
    context_object_name = 'appointments'
    paginate_by = 10
    ordering = ['appointment_date', 'appointment_time']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == 'patient':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'doctor':
            queryset = queryset.filter(doctor__user=user)
        # Admins and Receptionists see all
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'My Appointments' if self.request.user.user_type in ['patient', 'doctor'] else 'All Appointments'
        return context

class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model = Appointment
    template_name = 'clinical_app/appointment_detail.html'
    context_object_name = 'appointment'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.user_type == 'patient':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'doctor':
            queryset = queryset.filter(doctor__user=user)
        return queryset

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Ensure the user has permission to view this specific appointment
        if self.request.user.user_type == 'patient' and obj.patient.user != self.request.user:
            raise Http404("You do not have permission to view this appointment.")
        if self.request.user.user_type == 'doctor' and obj.doctor.user != self.request.user:
            raise Http404("You do not have permission to view this appointment.")
        return obj

class AppointmentCreateView(LoginRequiredMixin, CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'clinical_app/appointment_form.html'
    success_url = reverse_lazy('appointment_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user # Pass the requesting user to the form
        return kwargs

    def form_valid(self, form):
        form.instance.scheduled_by = self.request.user # Record who scheduled it
        response = super().form_valid(form)

        log_activity(
            self.request.user,
            'CREATE',
            f'Scheduled new appointment for {form.instance.patient.user.get_full_name()} with {form.instance.doctor.user.get_full_name()} on {form.instance.appointment_date}',
            model_name='Appointment',
            object_id=form.instance.pk,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Appointment scheduled successfully.")
        return response

class AppointmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'clinical_app/appointment_form.html'
    context_object_name = 'appointment'

    def test_func(self):
        appointment = self.get_object()
        user = self.request.user
        # Admin or Receptionist can update any appointment
        if user.user_type in ['admin', 'receptionist']:
            return True
        # Doctor can update their own appointments
        if user.user_type == 'doctor' and hasattr(user, 'doctor') and appointment.doctor == user.doctor:
            return True
        # Patient can (potentially) update their own appointments (e.g., reschedule)
        if user.user_type == 'patient' and hasattr(user, 'patient') and appointment.patient == user.patient:
            return True
        return False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user # Pass the requesting user to the form
        return kwargs

    def form_valid(self, form):
        old_appointment_data = {field.name: getattr(self.object, field.name) for field in self.object._meta.fields}

        response = super().form_valid(form)

        # Capture changes for activity log
        detected_changes = {}
        for field, old_value in old_appointment_data.items():
            new_value = getattr(self.object, field)
            if str(old_value) != str(new_value):
                detected_changes[field] = {'old': str(old_value), 'new': str(new_value)}

        log_activity(
            self.request.user,
            'UPDATE',
            f'Updated appointment {self.object.pk} for {self.object.patient.user.get_full_name()} on {self.object.appointment_date}',
            model_name='Appointment',
            object_id=self.object.pk,
            ip_address=get_client_ip(self.request),
            changes=detected_changes if detected_changes else None
        )
        messages.success(self.request, "Appointment updated successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy('appointment_list')


class AppointmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Appointment
    template_name = 'clinical_app/confirm_delete.html'
    success_url = reverse_lazy('appointment_list')
    context_object_name = 'object'

    def test_func(self):
        appointment = self.get_object()
        user = self.request.user
        # Only admin or receptionist can delete
        return user.user_type in ['admin', 'receptionist']

    def form_valid(self, form):
        appointment = self.get_object()
        patient_name = appointment.patient.user.get_full_name()
        appointment_id = appointment.pk
        appointment_date = appointment.appointment_date

        response = super().form_valid(form)

        log_activity(
            self.request.user,
            'DELETE',
            f'Deleted appointment {appointment_id} for {patient_name} on {appointment_date}',
            model_name='Appointment',
            object_id=appointment_id,
            ip_address=get_client_ip(self.request)
        )
        messages.success(self.request, "Appointment deleted successfully.")
        return response

# --- Staff List Views (Admin Only) ---
class StaffListView(LoginRequiredMixin, IsAdminMixin, ListView):
    model = User
    template_name = 'clinical_app/staff_list.html'
    context_object_name = 'staff'
    paginate_by = 10
    # Exclude patients from the staff list
    queryset = User.objects.exclude(user_type='patient').order_by('last_name', 'first_name')

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(username__icontains=query) |
                Q(user_type__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'All Staff'
        return context

# --- Bed Management (Admin/Nurse) ---
class BedManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Ward
    template_name = 'clinical_app/bed_management.html'
    context_object_name = 'wards'
    queryset = Ward.objects.prefetch_related('beds').all()

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type in ['admin', 'nurse']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Bed Management'
        return context

# --- Department List (Admin) ---
class DepartmentListView(LoginRequiredMixin, IsAdminMixin, ListView):
    model = Department
    template_name = 'clinical_app/department_list.html'
    context_object_name = 'departments'
    ordering = ['name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Hospital Departments'
        return context

# --- Medication Inventory (Pharmacist/Admin/Procurement Officer) ---
class MedicationInventoryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Medication
    template_name = 'clinical_app/medication_inventory.html'
    context_object_name = 'medications'
    ordering = ['name']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'pharmacist', 'procurement_officer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['low_stock_meds'] = Medication.objects.filter(stock_quantity__lt=F('reorder_level')).order_by('name')
        context['title'] = 'Medication Inventory'
        return context

# --- Lab Reports (Lab Tech/Doctor/Admin) ---
class LabReportsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = LabTestResult
    template_name = 'clinical_app/lab_reports.html'
    context_object_name = 'results'
    paginate_by = 20
    ordering = ['-result_date']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor', 'lab_tech']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Doctors can see results for their patients' encounters
            queryset = queryset.filter(request__encounter__doctor=user.doctor).distinct()
        elif user.user_type == 'lab_tech' and hasattr(user, 'labtechnician'):
            # Lab techs can see results they performed or are assigned to
            queryset = queryset.filter(performed_by=user) # Or filter by lab if assigned
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lab Test Results'
        return context

# --- Imaging Reports (Radiologist/Doctor/Admin) ---
class ImagingReportsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ImagingResult
    template_name = 'clinical_app/imaging_reports.html'
    context_object_name = 'results'
    paginate_by = 20
    ordering = ['-report_date']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor', 'radiologist']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            queryset = queryset.filter(request__encounter__doctor=user.doctor).distinct()
        elif user.user_type == 'radiologist' and hasattr(user, 'radiologist'):
            queryset = queryset.filter(radiologist=user) # Or filter by imaging center/dept
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Imaging Reports'
        return context

# --- Cancer Registry Reports (Admin/Doctor) ---
class CancerRegistryReportsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CancerRegistryReport
    template_name = 'clinical_app/cancer_registry_reports.html'
    context_object_name = 'reports'
    paginate_by = 20
    ordering = ['-report_date']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor'] # Doctors might need to view their own

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            queryset = queryset.filter(patient__encounters__doctor=user.doctor).distinct() # Show reports for their patients
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cancer Registry Reports'
        return context

# --- Birth Records (Admin/Receptionist/Nurse) ---
class BirthRecordsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = BirthRecord
    template_name = 'clinical_app/birth_records.html'
    context_object_name = 'records'
    paginate_by = 20
    ordering = ['-date_of_birth']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Birth Records'
        return context

# --- Mortality Records (Admin/Receptionist/Doctor/Nurse) ---
class MortalityRecordsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = MortalityRecord
    template_name = 'clinical_app/mortality_records.html'
    context_object_name = 'records'
    paginate_by = 20
    ordering = ['-date_of_death']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'doctor', 'nurse']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Mortality Records'
        return context

# --- Activity Log (Admin Only) ---
class ActivityLogListView(LoginRequiredMixin, IsMedicalStaffMixin, ListView):
    model = ActivityLog
    template_name = 'logs/activity_log_list.html' # We'll create this template
    context_object_name = 'activity_logs'
    paginate_by = 20 # Show 20 logs per page
    ordering = ['-timestamp'] # Order by most recent first

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        action_type = self.request.GET.get('action_type')
        model_name = self.request.GET.get('model_name')

        if query:
            queryset = queryset.filter(
                Q(description__icontains=query) |
                Q(user__username__icontains=query) |
                Q(model_name__icontains=query) |
                Q(ip_address__icontains=query)
            )
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add options for filtering
        context['action_types'] = ActivityLog.objects.order_by().values_list('action_type', flat=True).distinct()
        context['model_names'] = ActivityLog.objects.order_by().values_list('model_name', flat=True).distinct()
        return context