from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.db import transaction # For atomic operations
from django.db.models import Q, Count, Case, When, BooleanField, F 
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
from django.db.models import Prefetch
import hashlib # For digital signature
from django.views.generic import DetailView, View
import logging
import base64
from django.core.files.base import ContentFile
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
import datetime 
from django.utils.timezone import now
import uuid
from django.utils import timezone

from .models import (
    User, Patient, Doctor, Pharmacist, Appointment, Encounter, VitalSign, MedicalHistory,
    PhysicalExamination, Diagnosis, TreatmentPlan, LabTestRequest, LabTestResult, # LabTestRequest needed
    ImagingRequest, ImagingResult, Prescription, CaseSummary, ConsentForm, # Prescription, ImagingRequest needed
    Ward, Bed, Department, LabTest, ImagingType, Medication, Nurse, # Added Nurse
    CancerRegistryReport, BirthRecord, MortalityRecord, ProcurementOfficer,
    Receptionist, LabTechnician, Radiologist, ClinicalNote,Ward, Bed # Ensure these are imported if they are distinct profiles
)

from .forms import (
    CustomUserCreationForm, PatientRegistrationForm, AppointmentForm, VitalSignForm,
    MedicalHistoryForm, PhysicalExaminationForm, DiagnosisForm, TreatmentPlanForm,
    LabTestRequestForm, LabTestResultForm, ImagingRequestForm, ImagingResultForm,
    PrescriptionForm, ConsentFormForm, DoctorForm, DoctorRegistrationForm,
    NurseRegistrationForm, PharmacistRegistrationForm, ProcurementOfficerRegistrationForm,
    CustomUserChangeForm, ReceptionistRegistrationForm, LabTechnicianRegistrationForm, 
    RadiologistRegistrationForm, ClinicalNoteForm, PatientForm, DepartmentForm, WardForm, BedCreateForm, BedUpdateForm,
    BirthRecordForm, MortalityRecordForm, MedicationForm, CancerRegistryReportForm, ImagingResultForm, LabTestResultForm, UserUpdateForm, ConsentSignatureUploadForm
)

from .models import ActivityLog
from django.contrib.auth.models import AnonymousUser
import json

logger = logging.getLogger(__name__)

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
                context['total_active_users'] = User.objects.filter(is_active=True).count()
                # context['total_active_staff'] = User.objects.filter(is_active=True).exclude(user_type='patient').count()
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
                    report_date__gte=one_year_ago 
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
                        dispensed_by=pharmacist 
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
    'admin': 'AD', 
}

class UserRegistrationView(CreateView):
    template_name = 'clinical_app/user_management/register.html'
    success_url = reverse_lazy('login') # This will be the fallback if no specific redirect is hit

    def get_form_class(self):
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
            return CustomUserCreationForm
        else:
            messages.error(self.request, "Invalid or unsupported user type for registration. Please choose a valid type.")
            # It's better to redirect to a selection page or raise a Http404 here
            # For now, returning CustomUserCreationForm might lead to immediate form_invalid
            return CustomUserCreationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user_type_from_url = self.kwargs.get('user_type', None)
        kwargs['user_type'] = user_type_from_url
        logger.debug(f"##### [UserRegistrationView.get_form_kwargs] user_type from URL kwargs: '{user_type_from_url}'. kwargs passed to form: {kwargs}")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_type = self.kwargs.get('user_type', 'general')
        context['user_type'] = user_type
        context['display_user_type'] = user_type.replace('_', ' ').title()
        return context

    def form_valid(self, form):
        logger.debug(f"##### [UserRegistrationView.form_valid] Form is valid. Attempting to save user.")
        user_type = self.kwargs.get('user_type', 'general') # Get user_type from URL kwargs

        try:
            with transaction.atomic():
                # Pass user_type to form.save() for internal logic (username prefix, is_staff, etc.)
                # This is the FIRST and ONLY call to form.save() in this view's successful path.
                user = form.save(commit=True) # user_type is now handled internally by clean/save in the form

                # If the form's save method somehow fails to set _raw_password, handle it
                raw_password = getattr(user, '_raw_password', None)
                if raw_password is None:
                    logger.error(f"form.save() for {user.username} did not set _raw_password. Transaction rolled back.")
                    form.add_error(None, "An internal error occurred: password could not be generated. Please try again.")
                    # Manually raise ValidationError to ensure form_invalid is called and transaction rolls back
                    raise ValidationError("Password generation failed.")


                print(f"[VIEW DEBUG] Username: {user.username}")
                print(f"[VIEW DEBUG] Raw Password: {user._raw_password}")
                print(f"[VIEW DEBUG] Check Password Valid: {user.check_password(user._raw_password)}")

                # Create specific profile based on user type and cleaned data.
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
                    profile_instance = Doctor.objects.create(
                        user=user,
                        specialization=form.cleaned_data['specialization'],
                        medical_license_number=form.cleaned_data['medical_license_number'],
                        department=form.cleaned_data['department'],
                        years_of_experience=form.cleaned_data.get('years_of_experience'), # Use .get() for optional fields
                    )
                elif user_type == 'nurse':
                    profile_instance = Nurse.objects.create(
                        user=user,
                        nursing_license_number=form.cleaned_data.get('nursing_license_number'),
                        assigned_ward=form.cleaned_data.get('assigned_ward'),
                    )
                elif user_type == 'pharmacist':
                    profile_instance = Pharmacist.objects.create(
                        user=user,
                        pharmacy_license_number=form.cleaned_data.get('pharmacy_license_number'),
                        years_of_experience=form.cleaned_data.get('years_of_experience'),
                    )
                elif user_type == 'procurement_officer':
                    profile_instance = ProcurementOfficer.objects.create(
                        user=user,
                        employee_id=form.cleaned_data.get('employee_id'),
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

                # Log successful user and profile creation.
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

                # Attempt to send email
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

                messages.info(self.request,
                                  f"New User: <strong>{user.username}</strong>, Temporary Password: <strong><span class='text-danger'>{raw_password}</span></strong>. "
                                  f"Please ensure the user logs in and changes their password immediately. "
                                  f"This message is for development purposes and will be removed in production.")

            # --- Important: Handle Redirection after successful transaction ---
            # THIS IS WHERE YOU RETURN A REDIRECT, NOT super().form_valid(form)
            if user_type == 'patient':
                return redirect('patient_dashboard') # Assuming you have a URL named 'patient_dashboard'
            elif user_type == 'doctor':
                return redirect('doctor_dashboard') # Assuming you have 'doctor_dashboard'
            # Add more specific redirects for other user types if they have dedicated dashboards
            elif user_type == 'admin':
                return redirect(reverse_lazy('admin:index')) # Redirect admin to Django admin
            else:
                # Fallback redirect for other roles or generic success
                return redirect('registration_success') # Ensure you have this URL or use 'login'

        except ValidationError as e:
            # Catch specific form validation errors (e.g., from clean() or form.add_error in save())
            logger.warning(f"Form ValidationError during registration: {e.message}")
            messages.error(self.request, f"Registration failed: {e.message}")
            return self.form_invalid(form) # Re-render form with errors
        except Exception as e:
            # Catch any other unexpected errors during the transaction
            logger.exception(f"An unexpected error occurred during {user_type} user registration for {form.cleaned_data.get('email')}: {e}")
            messages.error(self.request, "An unexpected error occurred during registration. Please contact support.")
            return self.form_invalid(form) # Re-render form with errors

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below to register the account.")
        logger.debug(f"##### [UserRegistrationView.form_invalid] Form errors: {form.errors}")
        return super().form_invalid(form) # This will render the form again with errors


class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'clinical_app/user_list.html' # We will create this template
    context_object_name = 'users'
    paginate_by = 20 # Adjust as needed
    ordering = ['first_name', 'last_name'] # Order users alphabetically

    def test_func(self):
        # Only allow 'admin' or 'receptionist' to view the full user list
        # Adjust permissions as per your application's requirements
        return self.request.user.user_type in ['admin', 'receptionist']

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('q')

        if search_query:
            # Filter by first name, last name, username, or user type
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(user_type__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'All System Users'
        return context

class UserDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = User
    template_name = 'clinical_app/user_detail.html'
    context_object_name = 'user_obj' # Renamed to avoid clash with request.user

    def test_func(self):
        # Allow admin, or the user themselves, or receptionists to view user details
        user_obj = self.get_object()
        return (self.request.user.user_type == 'admin' or
                self.request.user.user_type == 'receptionist' or
                self.request.user == user_obj)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"User: {self.object.get_full_name() or self.object.username}"
        return context

class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = UserUpdateForm # Use the form we defined
    template_name = 'clinical_app/user_form.html' # Use a generic form template
    context_object_name = 'user_obj'

    def get_success_url(self):
        return reverse_lazy('user_detail', kwargs={'pk': self.object.pk})

    def test_func(self):
        # Only admin can update other users.
        # A user can update their OWN profile (e.g., patient updates their contact info)
        user_to_update = self.get_object()
        return (self.request.user.user_type == 'admin' or
                self.request.user == user_to_update)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update User: {self.object.get_full_name() or self.object.username}"
        context['is_update'] = True # Flag to indicate it's an update form
        return context

class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'clinical_app/user_confirm_delete.html'
    context_object_name = 'user_obj'
    success_url = reverse_lazy('user_list') # Redirect to user list after deletion

    def test_func(self):
        # Only admin can delete users.
        # An admin cannot delete their own account.
        user_to_delete = self.get_object()
        return (self.request.user.user_type == 'admin' and
                self.request.user != user_to_delete) # Prevent self-deletion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Delete User: {self.object.get_full_name() or self.object.username}"
        return context

class ConsentFormCreateView(LoginRequiredMixin, IsMedicalStaffMixin, CreateView):
    model = ConsentForm
    form_class = ConsentFormForm # This form no longer handles signature fields
    template_name = 'clinical_app/patient_consent_form.html'

    def get_success_url(self):
        # This will be overridden in form_valid for redirection to sign view
        return reverse_lazy('patient_detail', kwargs={'pk': self.kwargs['patient_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient'] = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        context['form_title'] = "Create New Consent Form" # Updated title
        return context

    def form_valid(self, form):
        form.instance.patient = get_object_or_404(Patient, pk=self.kwargs['patient_pk'])
        # Initially, the form is not signed
        form.instance.is_signed = False
        form.instance.signed_by_staff = None # Will be set by signing view if staff signs
        form.instance.signed_date = None # Will be set by signing view
        form.instance.signature_image = None # Ensure it's empty

        # Save the consent form (it's created as unsigned)
        response = super().form_valid(form) # form.instance now has the ID

        messages.success(self.request, f"Consent Form '{form.instance.consent_type}' created successfully. Now, please sign it.")
        # Redirect to the new signing view, passing the newly created consent form's PK
        return redirect(reverse('sign_consent_form', kwargs={'pk': form.instance.pk}))

# clinical_app/views.py (continued)
class SignConsentFormView(LoginRequiredMixin, IsMedicalStaffMixin, View):
    template_name = 'clinical_app/patient_consent_form_sign.html' # The HTML you provided

    def get(self, request, pk, *args, **kwargs):
        consent_form = get_object_or_404(ConsentForm, pk=pk)
        context = {
            'consent_form': consent_form,
            'form_title': "Sign Consent Form",
        }
        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        consent_form = get_object_or_404(ConsentForm, pk=pk)
        form = ConsentSignatureUploadForm(request.POST)

        if form.is_valid():
            signature_data_url = form.cleaned_data['signature_data']

            # Expected format: "data:image/png;base64,iVBORw0KGgo..."
            if signature_data_url.startswith('data:image/png;base64,'):
                format, imgstr = signature_data_url.split(';base64,')
                ext = format.split('/')[-1] # Should be 'png'

                # Generate a unique filename
                file_name = f'signature_{uuid.uuid4()}.{ext}'
                data = ContentFile(base64.b64decode(imgstr), name=file_name)

                consent_form.signature_image.save(file_name, data, save=False) # save=False so we can update other fields first
                consent_form.is_signed = True
                consent_form.signed_date = timezone.now()
                consent_form.signed_by_staff = request.user # Assuming staff member is signing

                consent_form.save() # Now save the model instance with the image and updated fields

                messages.success(request, "Consent form signed successfully!")
                return redirect(reverse('patient_detail', kwargs={'pk': consent_form.patient.pk}))
            else:
                messages.error(request, "Invalid signature data format.")
        else:
            messages.error(request, "There was an error processing your signature.")

        context = {
            'consent_form': consent_form,
            'form_title': "Sign Consent Form",
            'form': form # Pass the form back to display errors if any
        }
        return render(request, self.template_name, context)

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
        context['consent_forms'] = patient.consent_forms.all().order_by('-id')

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
    form_class = PatientRegistrationForm
    template_name = 'clinical_app/patient_form.html'
    success_url = reverse_lazy('patient_list')

    def get_form_kwargs(self):
        """Pass user_type to the form to ensure proper username generation"""
        kwargs = super().get_form_kwargs()
        kwargs['user_type'] = 'Patient'  # Must match USER_TYPE_PREFIXES key exactly
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission with auto-generated credentials"""
        with transaction.atomic():
            # Save the User with auto-generated credentials
            user = form.save(commit=False)
            user.user_type = 'Patient'  # Must match USER_TYPE_PREFIXES key exactly
            user.save()

            # Create Patient profile
            patient = Patient.objects.create(
                user=user,
                blood_group=form.cleaned_data.get('blood_group'),
                emergency_contact_name=form.cleaned_data.get('emergency_contact_name'),
                emergency_contact_phone=form.cleaned_data.get('emergency_contact_phone'),
                allergies=form.cleaned_data.get('allergies'),
                pre_existing_conditions=form.cleaned_data.get('pre_existing_conditions'),
            )

            # Log activity
            log_activity(
                self.request.user,
                'CREATE',
                f'Created patient: {user.get_full_name()} (ID: {patient.pk})',
                model_name='Patient',
                object_id=patient.pk,
                ip_address=get_client_ip(self.request)
            )

            # Send welcome email with credentials
            try:
                send_mail(
                    subject='Your Patient Account Credentials',
                    message=f"""
                    Your account has been created successfully.
                    Username: {user.username}
                    Temporary Password: {user._raw_password}
                    """,
                    from_email='noreply@yourhospital.com',
                    recipient_list=[user.email],
                    fail_silently=False
                )
                email_status = "Credentials have been emailed"
            except Exception as e:
                email_status = "Error sending credentials email"
                logger.error(f"Failed to send credentials email: {str(e)}")

            messages.success(
                self.request,
                f"Patient {user.get_full_name()} created successfully. {email_status}."
            )
            return redirect(self.success_url)

    def form_invalid(self, form):
        """Handle invalid form submission"""
        messages.error(
            self.request,
            "Error creating patient. Please correct the errors below."
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Add context variables for template rendering"""
        context = super().get_context_data(**kwargs)
        # Add any additional context needed for template
        context['page_title'] = "Register New Patient"
        return context

# --- Patient Update View ---

class IsAdminUserMixin(LoginRequiredMixin): # Renamed for clarity
    permission_denied_message = "You are not authorized to perform this action. Only administrators can access this page."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission() # Redirect to login page

        # Check if the user is an 'admin' user_type or a superuser
        if not (request.user.user_type == 'admin' or request.user.is_superuser):
            messages.error(request, self.permission_denied_message)
            return redirect(reverse_lazy('home')) # Redirect to a safe page (e.g., dashboard)
        
        return super().dispatch(request, *args, **kwargs)


# --- Patient Update View ---
# UPDATED: Use the new IsAdminUserMixin
class PatientUpdateView(IsAdminUserMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = 'clinical_app/patient_form.html'
    context_object_name = 'patient'
    success_url = reverse_lazy('patient_list')
    success_message = "Patient profile for '%(user.get_full_name)s' updated successfully!"

    def get_success_message(self, cleaned_data):
        return self.success_message % {'user.get_full_name': self.object.user.get_full_name()}

    def form_valid(self, form):
        messages.success(self.request, self.get_success_message(form.cleaned_data))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error updating the patient's profile. Please correct the errors below.")
        return super().form_invalid(form)


# --- Patient Delete View ---
# UPDATED: Use the new IsAdminUserMixin
class PatientDeleteView(IsAdminUserMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Patient
    template_name = 'clinical_app/patient_confirm_delete.html'
    context_object_name = 'patient'
    success_url = reverse_lazy('patient_list')
    success_message = "Patient '%(user.get_full_name)s' (ID: %(patient_id)s) successfully deleted."

    def get_success_message(self, cleaned_data):
        return self.success_message % {
            'user.get_full_name': self.object.user.get_full_name(),
            'patient_id': self.object.patient_id
        }

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_message = self.get_success_message({})
        
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, success_message)
        return response

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


# --- Patient List View (Consider who should see this list) ---
# If only admins should see the list of all patients, apply the mixin here too.
# Otherwise, if other staff types (like doctors/nurses) should see the list but not edit,
# then keep a different mixin or no custom mixin.

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
        
        # --- MODIFICATION AND DEBUGGING STARTS HERE ---
        lab_requests = LabTestRequest.objects.filter(encounter=encounter).order_by('-requested_date')
        
        print("\n--- Debugging Lab Test Requests in EncounterDetailView ---") # Debug print
        processed_lab_requests = [] # Create a new list to store processed requests for debugging clarity
        for req in lab_requests:
            original_status = req.status
            
            # Call the get_status_badge_class method on each LabTestRequest object
            # and attach the returned class string as a new attribute 'badge_class'
            badge_class_from_method = req.get_status_badge_class() 
            req.badge_class = badge_class_from_method
            
            # Debug prints to see the values
            print(f"  Lab Request ID: {req.pk}")
            print(f"  Original Status from DB: '{original_status}'")
            print(f"  Returned Badge Class from get_status_badge_class(): '{badge_class_from_method}'")
            print(f"  Assigned req.badge_class attribute: '{req.badge_class}'")
            
            processed_lab_requests.append(req) # Add the processed request to the new list
        context['lab_requests'] = processed_lab_requests # Assign the processed list to context
        print("--- End Debugging Lab Test Requests ---\n") # Debug print
        # --- MODIFICATION AND DEBUGGING ENDS HERE ---

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

# Generate case summary
class GenerateCaseSummaryView(LoginRequiredMixin, IsMedicalStaffMixin, View):
    def post(self, request, pk, *args, **kwargs):
        encounter = get_object_or_404(Encounter, pk=pk)

        if not (request.user.user_type in ['doctor', 'nurse', 'admin'] or request.user.is_superuser):
            messages.error(request, "You are not authorized to prepare case summaries.")
            return redirect(reverse('encounter_detail', kwargs={'pk': encounter.pk}))

        try:
            doctor_instance = request.user.doctor
        except Exception:
            messages.error(request, "You are not registered as a doctor.")
            return redirect(reverse('encounter_detail', kwargs={'pk': encounter.pk}))

        encounter_for_summary = Encounter.objects.select_related(
            'patient__user', 'doctor__user', 'ward', 'bed'
        ).prefetch_related(
            'vital_signs',
            Prefetch(
                'patient__medical_history_entries',
                queryset=MedicalHistory.objects.select_related('recorded_by').order_by('-recorded_date'),
                to_attr='_patient_medical_histories'
            ),
            Prefetch(
                'physical_examinations',
                queryset=PhysicalExamination.objects.select_related('examined_by').order_by('-examination_date'),
                to_attr='prefetched_physical_examinations'
            ),
            Prefetch(
                'diagnoses',
                queryset=Diagnosis.objects.select_related('diagnosed_by').order_by('-diagnosis_date'),
                to_attr='prefetched_diagnoses'
            ),
            Prefetch(
                'treatment_plans',
                queryset=TreatmentPlan.objects.select_related('created_by').order_by('-created_date'),
                to_attr='prefetched_treatment_plans'
            ),
            Prefetch(
                'prescriptions',
                queryset=Prescription.objects.select_related(
                    'medication', 'prescribed_by', 'dispensed_by'
                ).order_by('-prescription_date'),
                to_attr='prefetched_prescriptions'
            ),
            Prefetch(
                'lab_test_requests',
                queryset=LabTestRequest.objects.select_related('requested_by').prefetch_related(
                    'tests',
                    Prefetch(
                        'results',
                        queryset=LabTestResult.objects.select_related('test', 'performed_by').order_by('result_date'),
                        to_attr='prefetched_results_list'
                    )
                ).order_by('-requested_date'),
                to_attr='prefetched_lab_requests'
            ),
            # --- START OF FIX ---
            Prefetch(
                'imaging_requests', # This is correct: Prefetching ImagingRequests related to the Encounter
                queryset=ImagingRequest.objects.select_related('imaging_type', 'requested_by') # Also select related 'requested_by' for efficiency
                                   .select_related('result__radiologist'), # Select the OneToOne 'result' AND its 'radiologist'
                                   # Removed the inner Prefetch, as select_related is better for OneToOne.
                to_attr='prefetched_imaging_requests'
            ),
            # --- END OF FIX ---
        ).get(pk=pk)

        summary_parts = []
        summary_parts.append(f"--- Encounter Summary ---")
        summary_parts.append(f"Patient: {encounter_for_summary.patient.user.get_full_name()} (ID: {encounter_for_summary.patient.patient_id})")
        summary_parts.append(f"Encounter ID: {encounter_for_summary.pk}")
        summary_parts.append(f"Date: {encounter_for_summary.admission_date.strftime('%Y-%m-%d %H:%M') if encounter_for_summary.admission_date else 'N/A'}")
        summary_parts.append(f"Attending Doctor: {encounter_for_summary.doctor.user.get_full_name() if encounter_for_summary.doctor else 'N/A'}")
        summary_parts.append(f"Department: {encounter_for_summary.ward.name if encounter_for_summary.ward else 'N/A'}")
        summary_parts.append(f"Ward: {encounter_for_summary.ward.name if encounter_for_summary.ward else 'N/A'}, Bed: {encounter_for_summary.bed.bed_number if encounter_for_summary.bed else 'N/A'}")

        summary_parts.append("\n--- Vital Signs ---")
        vitals = encounter_for_summary.vital_signs.all().order_by('-timestamp')
        for vital in vitals:
            vitals_info = []
            if vital.temperature: vitals_info.append(f"Temp: {vital.temperature}°C")
            if vital.blood_pressure_systolic and vital.blood_pressure_diastolic:
                vitals_info.append(f"BP: {vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg")
            if vital.heart_rate: vitals_info.append(f"HR: {vital.heart_rate} BPM")
            if vital.respiratory_rate: vitals_info.append(f"RR: {vital.respiratory_rate} BPM")
            if vital.oxygen_saturation: vitals_info.append(f"O2 Sat: {vital.oxygen_saturation}%")
            summary_parts.append(f"  {vital.timestamp.strftime('%Y-%m-%d %H:%M')}: {', '.join(vitals_info)}")

        summary_parts.append("\n--- Physical Examination ---")
        for pe in getattr(encounter_for_summary, 'prefetched_physical_examinations', []):
            examined_by = pe.examined_by.get_full_name() if pe.examined_by else "N/A"
            summary_parts.append(f"Examined on {pe.examination_date.strftime('%Y-%m-%d')} by {examined_by}")
            for field in ['general_appearance', 'head_and_neck', 'chest_and_lungs', 'heart_and_circulation', 'abdomen', 'musculoskeletal', 'neurological', 'skin', 'other_findings']:
                value = getattr(pe, field)
                if value:
                    summary_parts.append(f"  {field.replace('_', ' ').title()}: {value}")

        summary_parts.append("\n--- Diagnoses ---")
        for diag in getattr(encounter_for_summary, 'prefetched_diagnoses', []):
            diagnosed_by = diag.diagnosed_by.get_full_name() if diag.diagnosed_by else "N/A"
            summary_parts.append(f"{diag.diagnosis_text} ({diag.icd10_code}) - {diag.get_diagnosis_status_display()} by {diagnosed_by}")

        summary_parts.append("\n--- Treatment Plans ---")
        for tp in getattr(encounter_for_summary, 'prefetched_treatment_plans', []):
            created_by = tp.created_by.get_full_name() if tp.created_by else "N/A"
            summary_parts.append(f"{tp.treatment_description} - {tp.get_status_display()} (Created by {created_by})")

        summary_parts.append("\n--- Prescriptions ---")
        for rx in getattr(encounter_for_summary, 'prefetched_prescriptions', []):
            summary_parts.append(f"{rx.medication.name} ({rx.route}): {rx.dosage} - {rx.frequency} - {rx.duration}")
        summary_parts.append("\n--- Lab Tests ---")
        for req in getattr(encounter_for_summary, 'prefetched_lab_requests', []):
            test_names = ", ".join([t.name for t in req.tests.all()])
            summary_parts.append(f"Requested: {test_names} on {req.requested_date.strftime('%Y-%m-%d')}")
            for result in getattr(req, 'prefetched_results_list', []):
                summary_parts.append(f"  {result.test.name}: {result.result_value} {result.result_unit}")

        summary_parts.append("\n--- Imaging Requests ---")
        # Access the prefetched imaging requests
        for img_req in getattr(encounter_for_summary, 'prefetched_imaging_requests', []):
            summary_parts.append(f"{img_req.imaging_type.name} on {img_req.requested_date.strftime('%Y-%m-%d')}")
            # Access the related result via the 'result' attribute
            # Check if 'result' exists, as OneToOneField can be null on the reverse side if no result is linked
            if hasattr(img_req, 'result'):
                # The 'result' and its 'radiologist' are already loaded due to select_related
                summary_parts.append(f"  Findings: {img_req.result.findings}, Impression: {img_req.result.impression}")
                if img_req.result.radiologist:
                    summary_parts.append(f"  Reported by: {img_req.result.radiologist.get_full_name()}")
                if img_req.result.report_date:
                    summary_parts.append(f"  Report Date: {img_req.result.report_date.strftime('%Y-%m-%d %H:%M')}")


        final_summary_text = "\n".join(summary_parts)

        case_summary, created = CaseSummary.objects.update_or_create(
            encounter=encounter,
            defaults={
                'summary_text': final_summary_text,
                'prepared_by': doctor_instance,
                'is_signed': False,
                'signed_by_user': None,
                'user_signature_image': None,
                'user_initials': None,
                'date_signed': None,
                'digital_signature_hash': None,
            }
        )

        log_activity(
            request.user,
            'CREATE' if created else 'UPDATE',
            f'{"Generated" if created else "Updated"} draft case summary for patient {encounter.patient.user.get_full_name()} (Encounter ID: {encounter.pk})',
            model_name='CaseSummary',
            object_id=case_summary.pk,
            ip_address=get_client_ip(request)
        )

        messages.success(request, f"Case Summary draft for Encounter {encounter.pk} successfully {'created' if created else 'updated'}. Please sign to finalize.")
        return redirect(reverse('sign_case_summary', kwargs={'pk': case_summary.pk}))

class SignCaseSummaryView(LoginRequiredMixin, View):
    def get(self, request, pk):
        summary = get_object_or_404(CaseSummary, pk=pk)
        return render(request, 'clinical_app/case_summary_sign.html', {'summary': summary})

    def post(self, request, pk):
        summary = get_object_or_404(CaseSummary, pk=pk)

        signature_data = request.POST.get("signature_data")
        if not signature_data:
            messages.error(request, "No signature provided.")
            return redirect('sign_case_summary', pk=pk)

        # Decode the base64 string
        format, imgstr = signature_data.split(';base64,')
        ext = format.split('/')[-1]
        file_name = f'signature_{request.user.username}_{pk}.{ext}'

        summary.user_signature_image.save(file_name, ContentFile(base64.b64decode(imgstr)), save=True)
        summary.is_signed = True
        summary.signed_by_user = request.user
        summary.date_signed = now()
        summary.save()

        messages.success(request, "Signature successfully saved.")
        return redirect(reverse('case_summary_detail', kwargs={'pk': summary.pk}))

# --- NEW VIEW FOR DISPLAYING CASE SUMMARY ---
class CaseSummaryDetailView(LoginRequiredMixin, IsMedicalStaffMixin, View):
    def get(self, request, pk, *args, **kwargs):
        # Fetch the CaseSummary object along with related data for the template
        case_summary = get_object_or_404(
            CaseSummary.objects.select_related(
                'encounter__patient__user',
                'encounter__doctor__user',
                'prepared_by__user',
                'encounter__ward',
                'encounter__bed',
                'encounter__appointment', # Select related if you want to display appointment details
            ),
            pk=pk
        )

        # Split the summary text into lines for easier display in the template
        summary_lines = case_summary.summary_text.split('\n')

        context = {
            'case_summary': case_summary,
            'summary_lines': summary_lines,
        }
        return render(request, 'clinical_app/case_summary_detail.html', context)


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
        context['consent_forms'] = patient.consent_forms.all().order_by('-id')

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

# Doctorlist and detailview
class DoctorListView(LoginRequiredMixin, IsMedicalStaffMixin, ListView):
    model = Doctor # <--- CORRECTED: Should be Doctor, not Patient
    template_name = 'clinical_app/doctor_list.html'
    context_object_name = 'doctors'
    paginate_by = 10
    ordering = ['user__last_name', 'user__first_name']

    def get_queryset(self):
        # Optimize query: select_related the User and Department associated with Doctor
        queryset = super().get_queryset().select_related('user', 'department')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(medical_license_number__icontains=query) | # <--- CORRECTED: Search by doctor's license
                Q(specialization__icontains=query) |       # <--- ADDED: Search by specialization
                Q(user__username__icontains=query)
            )
        return queryset


class DoctorDetailView(LoginRequiredMixin, IsMedicalStaffMixin, DetailView):
    model = Doctor
    template_name = 'clinical_app/doctor_detail.html'
    context_object_name = 'doctor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.get_object() # Get the Doctor object

        # No extra querysets for related items (vitals, diagnoses, prescriptions)
        # as per your request to just have biographic info.
        # The 'doctor' object itself (which includes doctor.user) will be passed to the template.

        # Log doctor viewing activity
        log_activity(
            self.request.user,
            'VIEW',
            f'Viewed doctor record: {doctor.user.get_full_name()} (License: {doctor.medical_license_number})',
            model_name='Doctor',
            object_id=doctor.pk,
            ip_address=get_client_ip(self.request)
        )
        return context

# --- Doctor Update View ---
class DoctorUpdateView(LoginRequiredMixin, IsMedicalStaffMixin, SuccessMessageMixin, UpdateView):
    model = Doctor
    form_class = DoctorForm
    template_name = 'clinical_app/doctor_form.html' # Use a generic form template
    context_object_name = 'doctor'
    success_url = reverse_lazy('doctor_list') # Redirect to doctor list after successful update
    success_message = "Doctor profile for '%(user.get_full_name)s' updated successfully!"

    def get_success_message(self, cleaned_data):
        # Custom success message to include doctor's name
        return self.success_message % {'user.get_full_name': self.object.user.get_full_name()}

    def form_valid(self, form):
        # You might want to add activity logging here
        messages.success(self.request, self.get_success_message(form.cleaned_data))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error updating the doctor's profile. Please correct the errors below.")
        return super().form_invalid(form)


# --- Doctor Delete View ---
class DoctorDeleteView(LoginRequiredMixin, IsMedicalStaffMixin, SuccessMessageMixin, DeleteView):
    model = Doctor
    template_name = 'clinical_app/doctor_confirm_delete.html' # Separate template for confirmation
    context_object_name = 'doctor'
    success_url = reverse_lazy('doctor_list') # Redirect to doctor list after deletion
    success_message = "Doctor '%(user.get_full_name)s' successfully deleted."

    def get_success_message(self, cleaned_data):
        # Access the object being deleted via self.object
        return self.success_message % {'user.get_full_name': self.object.user.get_full_name()}

    def delete(self, request, *args, **kwargs):
        # Override delete to add custom success message via messages framework
        self.object = self.get_object()
        success_message = self.get_success_message({}) # Pass empty dict if not using cleaned_data
        
        # Before deleting the Doctor instance, delete its associated User
        # This is critical for OneToOneField where Doctor depends on User
        user_to_delete = self.object.user
        response = super().delete(request, *args, **kwargs)
        user_to_delete.delete() # Explicitly delete the user

        messages.success(self.request, success_message)
        return response

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to display the delete confirmation page.
        """
        # Ensure the object exists before rendering the confirmation page
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests for deletion.
        """
        return self.delete(request, *args, **kwargs)

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
        # This line assumes your Patient model has an 'is_active' field
        # If Patient model is directly your User model, then user__is_active applies
        # form.fields['patient'].queryset = Patient.objects.filter(is_active=True)
        # If Patient links to User:
        # form.fields['patient'].queryset = Patient.objects.filter(user__is_active=True)

        # Filter doctors to only show active ones
        form.fields['doctor'].queryset = Doctor.objects.filter(user__is_active=True)

        # Filter wards and beds
        form.fields['ward'].queryset = Ward.objects.all()

        # Handle bed queryset for CreateView
        # On initial GET request, 'ward' won't be in self.request.POST,
        # so beds should typically be empty or filtered by a default ward
        # If it's a POST request (form submission), we try to filter beds based on the submitted ward
        if 'ward' in self.request.POST:
            try:
                ward_id = int(self.request.POST.get('ward'))
                form.fields['bed'].queryset = Bed.objects.filter(ward_id=ward_id, is_occupied=False)
            except (ValueError, TypeError):
                # Fallback if ward_id is invalid
                form.fields['bed'].queryset = Bed.objects.none()
        else:
            # For the initial GET request to display the form, or if no ward is selected
            # You generally want to start with an empty bed queryset for dynamic loading via JS
            form.fields['bed'].queryset = Bed.objects.none()

        # Removed the 'elif self.instance.pk:' part because CreateView doesn't have self.instance.pk
        # This logic is typically for an UpdateView

        return form

    def form_valid(self, form):
        # Set the doctor BEFORE saving the form if it's not already set
        if not form.cleaned_data.get('doctor') and self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.instance.doctor = self.request.user.doctor

        with transaction.atomic():
            # Call super().form_valid(form) FIRST to save the instance
            # At this point, form.instance will be populated with the new Encounter object
            response = super().form_valid(form)

            # If a bed was assigned, mark it as occupied
            if form.instance.bed:
                bed = form.instance.bed
                # Check if the bed was already occupied to avoid redundant updates and logs
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

class MedicationInventoryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Displays a list of all medications in inventory, including low stock items.
    Accessible to admins, pharmacists, and procurement officers.
    """
    model = Medication
    template_name = 'clinical_app/medication_inventory.html'
    context_object_name = 'medications'
    ordering = ['name'] # Order alphabetically by name

    def test_func(self):
        # Only admins, pharmacists, and procurement officers can view the inventory
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'pharmacist', 'procurement_officer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filter for low stock medications
        context['low_stock_meds'] = Medication.objects.filter(stock_quantity__lt=F('reorder_level')).order_by('name')
        context['title'] = 'Medication Inventory'
        return context

class MedicationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Handles the creation of a new Medication record.
    Accessible to admins and procurement officers.
    """
    model = Medication
    form_class = MedicationForm # Create this form in clinical_app/forms.py
    template_name = 'clinical_app/medication_form.html' # Template for the form
    success_url = reverse_lazy('medication_inventory_list') # Redirect after creation

    def test_func(self):
        # Only admins and procurement officers can add new medications
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'procurement_officer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Medication'
        return context

class MedicationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the detailed information of a single Medication.
    Accessible to admins, pharmacists, and procurement officers.
    """
    model = Medication
    template_name = 'clinical_app/medication_detail.html' # Template for medication details
    context_object_name = 'medication' # How the single object will be referred to in the template

    def test_func(self):
        # Admins, pharmacists, and procurement officers can view medication details
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'pharmacist', 'procurement_officer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Medication Details'
        return context

class MedicationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Handles the updating of an existing Medication record.
    Accessible to admins and procurement officers.
    """
    model = Medication
    form_class = MedicationForm # Reuse the same form for updating
    template_name = 'clinical_app/medication_form.html' # Reuse the form template
    success_url = reverse_lazy('medication_inventory_list') # Redirect after update

    def test_func(self):
        # Only admins and procurement officers can update medications
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'procurement_officer']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Medication'
        return context

class MedicationDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Handles the deletion of a Medication record.
    Typically restricted to administrators for data integrity.
    """
    model = Medication
    template_name = 'clinical_app/medication_confirm_delete.html' # Template for delete confirmation
    success_url = reverse_lazy('medication_inventory_list') # Redirect after deletion

    def test_func(self):
        # Only admin can delete medications
        return self.request.user.is_authenticated and \
               self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Medication'
        return context

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
        form.instance.recorded_by = self.request.user # Assuming a direct link

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
        form.instance.examined_by = self.request.user

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
        form.instance.diagnosed_by = self.request.user

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
    template_name = 'clinical_app/treatment_plan_create.html'

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
        form.instance.created_by = self.request.user

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
        form.instance.requested_by = self.request.user

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
    template_name = 'clinical_app/lab_test_form.html'

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

# --- NEW VIEWS FOR LAB TEST RESULTS ---

# --- NEW: LabTestRequestListView ---
class LabTestRequestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Displays a list of Lab Test Requests.
    Accessible to admins, doctors (their own requests/patient requests), and lab technicians.
    """
    model = LabTestRequest
    template_name = 'clinical_app/lab_test_requests_list.html' # NEW TEMPLATE
    context_object_name = 'requests' # Different context name from results
    paginate_by = 20
    ordering = ['-requested_date'] # Order by request date

    def test_func(self):
        # Admins, Doctors, and Lab Technicians can view requests
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor', 'lab_technician']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Doctors see requests they made OR requests for their patients
            queryset = queryset.filter(Q(requested_by=user) | Q(encounter__doctor=user.doctor)).distinct()
        elif user.user_type == 'lab_technician':
            # Lab Technicians can see all requests to fulfill them
            # You might want to filter by status here, e.g., 'pending', 'received'
            pass

        # Optional: Add filters for status, date range etc. if desired
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lab Test Requests'
        # Assuming LabTestRequest has status_choices defined like ImagingRequest
        context['status_choices'] = LabTestRequest.status_choices if hasattr(LabTestRequest, 'status_choices') else []
        context['current_status_filter'] = self.request.GET.get('status', '')
        return context

class LabTestRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Allows a Doctor (who made the request) or an Admin to update a Lab Test Request.
    Lab Technicians typically only record results, not modify the request itself.
    """
    model = LabTestRequest
    form_class = LabTestRequestForm
    template_name = 'clinical_app/lab_test_request_form.html'
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Admins can update any request
        if user.user_type == 'admin':
            return True

        # Doctors can update requests they made, as long as it's not already completed
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            lab_request = self.get_object()
            return lab_request.requested_by == user and lab_request.status != 'completed'
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Lab Test Request'
        return context

    def get_success_url(self):
        return reverse_lazy('lab_test_request_detail', kwargs={'pk': self.object.pk})


class LabTestRequestDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Allows a Doctor (who made the request) or an Admin to delete a Lab Test Request.
    Deletion is usually restricted once a result has been recorded.
    """
    model = LabTestRequest
    template_name = 'clinical_app/lab_test_confirm_delete.html' # Re-use generic confirm_delete.html
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Admins can delete any request
        if user.user_type == 'admin':
            return True

        # Doctors can delete requests they made, as long as no results have been attached
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            lab_request = self.get_object()
            return lab_request.requested_by == user and not lab_request.results.exists() # Check for no results
        return False

    def get_success_url(self):
        # Redirect to the list of lab requests after deletion
        return reverse_lazy('lab_test_requests_list')


# --- Optional: LabTestRequestDetailView ---
class LabTestRequestDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = LabTestRequest
    template_name = 'clinical_app/lab_test_request_detail.html'
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        if user.user_type in ['admin', 'lab_technician']:
            return True

        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            lab_request = self.get_object()
            if lab_request.requested_by == user:
                return True
            if lab_request.encounter.doctor == user.doctor:
                return True
        return False

class LabTestResultListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Displays a list of Lab Test Results.
    Accessible to admins, doctors (for their patients), and lab technicians.
    """
    model = LabTestResult
    template_name = 'clinical_app/lab_test_results_list.html'
    context_object_name = 'results'
    paginate_by = 20
    ordering = ['-result_date'] # Most recent results first

    def test_func(self):
        # Admins, Lab Technicians can see all results. Doctors can see results for their patients.
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'lab_technician', 'doctor']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Doctors see only results for their patients' encounters
            queryset = queryset.filter(request__encounter__doctor=user.doctor).distinct()
        elif user.user_type == 'lab_technician' and hasattr(user, 'labtechnician'):
            # Lab technicians might see all results or just those they performed
            # For now, let's say they can see all to manage.
            # If only their own: queryset = queryset.filter(performed_by=user)
            pass

        # Apply filters from dashboard card links (e.g., for last 30 days)
        date_range = self.request.GET.get('date_range')
        if date_range == 'last_30_days':
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            queryset = queryset.filter(result_date__gte=thirty_days_ago)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lab Test Results'
        context['active_filters'] = self.request.GET.urlencode() # For pagination
        context['filtered_by_date_range'] = self.request.GET.get('date_range')

        # Add total for dashboard cards
        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        context['total_lab_tests_performed_last_30_days'] = LabTestResult.objects.filter(
            result_date__gte=thirty_days_ago
        ).count()
        return context

class LabTestResultDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the details of a single Lab Test Result.
    Accessible to admins, doctors (for their patients), and lab technicians.
    """
    model = LabTestResult
    template_name = 'clinical_app/lab_test_result_detail.html'
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Admins and Lab Technicians can view any result
        if user.user_type in ['admin', 'lab_technician']:
            return True

        # Doctors can view results for their patients
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            lab_result = self.get_object()
            return lab_result.request.encounter.doctor == user.doctor
        return False

class LabTestResultUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Allows a Lab Technician or Admin to update an existing Lab Test Result.
    """
    model = LabTestResult
    form_class = LabTestResultForm
    template_name = 'clinical_app/lab_test_result_form.html'
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        # Only the lab technician who performed it, or an admin, can update
        if user.user_type == 'admin':
            return True
        if user.user_type == 'lab_technician':
            return self.get_object().performed_by == user
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Lab Test Result'
        return context

    def get_success_url(self):
        return reverse_lazy('lab_test_result_detail', kwargs={'pk': self.object.pk})

class LabTestResultDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Allows a Lab Technician or Admin to delete a Lab Test Result.
    """
    model = LabTestResult
    template_name = 'clinical_app/confirm_delete.html' # Re-use generic confirm_delete.html
    context_object_name = 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        # Only the lab technician who performed it, or an admin, can delete
        if user.user_type == 'admin':
            return True
        if user.user_type == 'lab_technician':
            return self.get_object().performed_by == user
        return False

    def get_success_url(self):
        # Redirect to the list after deletion
        return reverse_lazy('lab_test_results_list')


# --- Imaging Result Views ---

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
        form.instance.requested_by = self.request.user

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

class ImagingRequestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ImagingRequest
    template_name = 'clinical_app/imaging_requests_list.html' 
    context_object_name = 'requests' # Different context name
    paginate_by = 20
    ordering = ['-requested_date'] # Order by request date

    def test_func(self):
        # Admins, Doctors, and Radiologists can view requests
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor', 'radiologist']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Doctors see only requests they made or for their patients
            queryset = queryset.filter(Q(requested_by=user) | Q(encounter__doctor=user.doctor)).distinct()
        elif user.user_type == 'radiologist':
            # Radiologists might prioritize pending/scheduled requests
            # Or see all requests.
            # Example: Show only pending/scheduled for radiologists:
            # queryset = queryset.filter(status__in=['pending', 'scheduled'])
            pass # Currently, radiologist can see all requests.

        # Add filtering options if needed, e.g., by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Imaging Requests'
        context['status_choices'] = ImagingRequest.status_choices # To populate a filter dropdown
        context['current_status_filter'] = self.request.GET.get('status', '')
        # Add other context data as needed, e.g., for dashboard cards
        return context

class ImagingResultListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Displays a list of Imaging Results.
    Accessible to admins and radiologists. Doctors can see results for their patients.
    """
    model = ImagingResult
    template_name = 'clinical_app/imaging_results_list.html'
    context_object_name = 'results'
    paginate_by = 20
    # FIX 1: Change 'result_date' to 'report_date'
    ordering = ['-report_date'] # Most recent results first

    def test_func(self):
        # Admins and Radiologists can see all results. Doctors can see results for their patients.
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'radiologist', 'doctor']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Doctors see only results for their patients
            queryset = queryset.filter(request__patient__encounters__doctor=user.doctor).distinct()
        elif user.user_type == 'radiologist' and hasattr(user, 'radiologist'):
            # Radiologists might see results they've recorded or all results depending on policy.
            # For simplicity, let's say radiologist can see all or just their own.
            # If they should only see their own: queryset = queryset.filter(radiologist=user.radiologist)
            pass # Currently, radiologist can see all.

        # Apply filters from dashboard card links (e.g., for last 30 days)
        date_range = self.request.GET.get('date_range')
        if date_range == 'last_30_days':
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            # FIX 2: Change 'result_date__gte' to 'report_date__gte'
            queryset = queryset.filter(report_date__gte=thirty_days_ago)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Imaging Results'
        context['active_filters'] = self.request.GET.urlencode() # For pagination
        context['filtered_by_date_range'] = self.request.GET.get('date_range')
        return context

# --- NEW: ImagingRequestDetailView ---
class ImagingRequestDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the details of a single Imaging Request.
    Accessible to admins, radiologists, and doctors (if it's their patient's request or they requested it).
    """
    model = ImagingRequest
    template_name = 'clinical_app/imaging_request_detail.html'
    context_object_name = 'object' # Default context name for DetailView is 'object'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Admins and Radiologists can view any request
        if user.user_type in ['admin', 'radiologist']:
            return True

        # Doctors can view requests associated with their patients or requests they made
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            imaging_request = self.get_object()
            if imaging_request.requested_by == user: # Doctor made the request
                return True
            if imaging_request.encounter.doctor == user.doctor: # Request is for their patient
                return True
        return False


class ImagingResultCreateView(LoginRequiredMixin, IsRadiologistMixin, CreateView):
    """
    Handles the creation of a new Imaging Result for a specific ImagingRequest.
    Accessible only to radiologists.
    """
    model = ImagingResult
    form_class = ImagingResultForm
    template_name = 'clinical_app/sub_form.html' # As specified in your snippet

    def get_success_url(self):
        imaging_request_pk = self.kwargs.get('imaging_request_pk')
        if imaging_request_pk:
            imaging_request = get_object_or_404(ImagingRequest, pk=imaging_request_pk)
            # Redirect to the encounter detail view if available
            if imaging_request.encounter:
                messages.success(self.request, "Imaging result recorded successfully and request marked as complete.")
                return reverse_lazy('encounter_detail', kwargs={'pk': imaging_request.encounter.pk})
            # Fallback if no encounter linked, redirect to the imaging request detail
            messages.success(self.request, "Imaging result recorded successfully and request marked as complete.")
            return reverse_lazy('imaging_request_detail', kwargs={'pk': imaging_request_pk}) # Assuming you have this URL
        return reverse_lazy('home') # Ultimate fallback

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        imaging_request_pk = self.kwargs.get('imaging_request_pk')
        context['imaging_request'] = get_object_or_404(ImagingRequest, pk=imaging_request_pk)
        context['form_title'] = f"Record Result for {context['imaging_request'].imaging_type.name} (Request #{imaging_request_pk})"
        return context

    def form_valid(self, form):
        imaging_request = get_object_or_404(ImagingRequest, pk=self.kwargs['imaging_request_pk'])
        form.instance.request = imaging_request
        # Assuming the radiologist is the current user linked to a Radiologist profile.
        # You might need a way to get the Radiologist instance from self.request.user.
        # For now, let's assume `radiologist` field on ImagingResult can take a User directly,
        # or you map `self.request.user.radiologist` if you have a Radiologist model.
        # If your `ImagingResult.radiologist` field is ForeignKey to Doctor, then:
        # form.instance.radiologist = self.request.user.doctor if hasattr(self.request.user, 'doctor') else None
        # Or, if you have a dedicated Radiologist model linked to User:
        if hasattr(self.request.user, 'radiologist'): # Assuming `user.radiologist` exists
            form.instance.radiologist = self.request.user
        else:
            # Handle case where user is radiologist type but no radiologist profile linked
            # This might indicate a data setup issue or require a fallback
            messages.error(self.request, "Radiologist profile not found for the logged-in user.")
            return self.form_invalid(form)


        with transaction.atomic():
            response = super().form_valid(form) # Save the ImagingResult

            # Update the status of the ImagingRequest
            if imaging_request.status != 'completed':
                old_status = imaging_request.status
                imaging_request.status = 'completed'
                imaging_request.save()

                log_activity(
                    self.request.user,
                    'UPDATE',
                    f'Imaging request status updated to completed for {imaging_request.encounter.patient.user.get_full_name()} (Request ID: {imaging_request.pk})',
                    model_name='ImagingRequest',
                    object_id=imaging_request.pk,
                    ip_address=get_client_ip(self.request),
                    changes={'status': {'old': old_status, 'new': 'completed'}}
                )

            log_activity(
                self.request.user,
                'CREATE',
                f'Recorded imaging result for patient {imaging_request.encounter.patient.user.get_full_name()} (Request ID: {imaging_request.pk}, Result ID: {form.instance.pk})',
                model_name='ImagingResult',
                object_id=form.instance.pk,
                ip_address=get_client_ip(self.request)
            )
            messages.success(self.request, "Imaging result recorded successfully and request marked as complete.")
        return response

class ImagingResultDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the detailed information of a single Imaging Result.
    Accessible to admins, radiologists, and doctors (for their patients).
    """
    model = ImagingResult
    template_name = 'clinical_app/imaging_result_detail.html'
    context_object_name = 'result'

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.user_type in ['admin', 'radiologist']:
            return True
        if user.user_type == 'doctor' and hasattr(user, 'doctor'):
            # Allow doctor to view if the result is for their patient's request
            result = self.get_object()
            return result.request.patient.encounters.filter(doctor=user.doctor).exists()
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Imaging Result Details'
        return context

class ImagingResultUpdateView(LoginRequiredMixin, IsRadiologistMixin, UpdateView):
    """
    Handles the updating of an existing Imaging Result.
    Accessible only to radiologists.
    """
    model = ImagingResult
    form_class = ImagingResultForm
    template_name = 'clinical_app/imaging_result_form.html' # Use a dedicated form template for general update
    success_url = reverse_lazy('imaging_results_list') # Redirect to the general list after update

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Imaging Result'
        return context

class ImagingResultDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Handles the deletion of an Imaging Result.
    Typically restricted to administrators for data integrity.
    """
    model = ImagingResult
    template_name = 'clinical_app/imaging_result_confirm_delete.html'
    success_url = reverse_lazy('imaging_results_list')

    def test_func(self):
        # Only admin can delete imaging results
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Imaging Result'
        return context
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
        form.instance.prescribed_by = self.request.user
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

# What has been done to the patient
# View to create a Clinical Note for a specific Encounter
class ClinicalNoteCreateView(LoginRequiredMixin, CreateView):
    model = ClinicalNote
    form_class = ClinicalNoteForm # Use a ModelForm
    template_name = 'clinical_app/clinical_note_form.html' # Create this template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encounter_pk = self.kwargs.get('encounter_pk')
        encounter = get_object_or_404(Encounter, pk=encounter_pk)
        context['encounter'] = encounter
        context['patient'] = encounter.patient # For displaying patient name in template
        return context

    def form_valid(self, form):
        encounter_pk = self.kwargs.get('encounter_pk')
        encounter = get_object_or_404(Encounter, pk=encounter_pk)
        form.instance.encounter = encounter
        form.instance.created_by = self.request.user # Assign the logged-in user
        return super().form_valid(form)

    def get_success_url(self):
        # Redirect to the detail view of the newly created clinical note
        # Or to the encounter detail page
        return reverse('clinical_note_detail', kwargs={
            'encounter_pk': self.kwargs['encounter_pk'],
            'pk': self.object.pk
        })

# View to display a Clinical Note
class ClinicalNoteDetailView(LoginRequiredMixin, DetailView):
    model = ClinicalNote
    template_name = 'clinical_app/clinical_note_detail.html' # Create this template
    context_object_name = 'clinical_note' # Renames 'object' to 'clinical_note' in template

    def get_object(self, queryset=None):
        encounter_pk = self.kwargs.get('encounter_pk')
        clinical_note_pk = self.kwargs.get('pk')
        # Ensure the note belongs to the specified encounter
        return get_object_or_404(
            ClinicalNote,
            pk=clinical_note_pk,
            encounter__pk=encounter_pk
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add encounter and patient to context for consistent headers/navigation
        context['encounter'] = self.object.encounter
        context['patient'] = self.object.encounter.patient
        return context

# You might also want an UpdateView for Clinical Notes
class ClinicalNoteUpdateView(LoginRequiredMixin, UpdateView):
    model = ClinicalNote
    form_class = ClinicalNoteForm
    template_name = 'clinical_app/clinical_note_form.html' 
    context_object_name = 'clinical_note'

    def get_object(self, queryset=None):
        encounter_pk = self.kwargs.get('encounter_pk')
        clinical_note_pk = self.kwargs.get('pk')
        return get_object_or_404(
            ClinicalNote,
            pk=clinical_note_pk,
            encounter__pk=encounter_pk
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['encounter'] = self.object.encounter
        context['patient'] = self.object.encounter.patient
        return context

    def get_success_url(self):
        return reverse('clinical_note_detail', kwargs={
            'encounter_pk': self.kwargs['encounter_pk'],
            'pk': self.object.pk
        })

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

def search_patients_ajax(request):
    """
    API endpoint to search patients by name or ID.
    Returns JSON for Select2.
    """
    query = request.GET.get('q', '')
    patients = Patient.objects.filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__username__icontains=query) | # search by username too
        Q(patient_id__icontains=query) # if you have a specific patient_id field
    ).order_by('user__first_name', 'user__last_name')[:10] # Limit results

    results = []
    for patient in patients:
        results.append({
            'id': patient.pk,
            'text': f"{patient.user.get_full_name()} (ID: {patient.patient_id or 'N/A'})" # Or however you want to display
        })
    return JsonResponse({'results': results})

def search_doctors_ajax(request):
    """
    API endpoint to search doctors by name.
    Returns JSON for Select2.
    """
    query = request.GET.get('q', '')
    doctors = Doctor.objects.filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(user__username__icontains=query)
    ).order_by('user__first_name', 'user__last_name')[:10] # Limit results

    results = []
    for doctor in doctors:
        results.append({
            'id': doctor.pk,
            'text': f"Dr. {doctor.user.get_full_name()} ({doctor.specialization or 'N/A'})"
        })
    return JsonResponse({'results': results})


class AppointmentListView(LoginRequiredMixin, ListView):
    model = Appointment
    template_name = 'clinical_app/appointment_list.html'
    context_object_name = 'appointments'
    paginate_by = 15 # As per your template

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        search_query = self.request.GET.get('q') # Gets the 'q' parameter from the URL

        # 1. Apply user-specific filters first
        # This ensures users only see appointments relevant to them,
        # and then the search filter is applied on top of that.
        if user.user_type == 'patient':
            queryset = queryset.filter(patient__user=user)
        elif user.user_type == 'doctor':
            queryset = queryset.filter(doctor__user=user)
        # Admins and Receptionists (and other types) see all appointments by default

        # 2. Apply search filtering if a query exists
        if search_query:
            # Use Q objects for OR conditions across multiple fields
            queryset = queryset.filter(
                Q(patient__user__first_name__icontains=search_query) |
                Q(patient__user__last_name__icontains=search_query) |
                Q(doctor__user__first_name__icontains=search_query) |
                Q(doctor__user__last_name__icontains=search_query) |
                Q(reason_for_visit__icontains=search_query)
            )

        # 3. Apply ordering after all filters
        queryset = queryset.order_by('-id') # Orders by newest first

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'My Appointments' if self.request.user.user_type in ['patient', 'doctor'] else 'All Appointments'
        # The 'q' value is already in request.GET.q, so no need to explicitly add it to context
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
        form.instance.scheduled_by = self.request.user

        # Auto-assign patient/doctor based on user type if field is hidden
        if self.request.user.user_type == 'patient' and hasattr(self.request.user, 'patient'):
            form.instance.patient = self.request.user.patient
        elif self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
            form.instance.doctor = self.request.user.doctor

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

class WardListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Ward
    template_name = 'clinical_app/ward_list.html'
    context_object_name = 'wards'
    
    # *** CRITICAL FIX: Use distinct names for annotated fields ***
    queryset = Ward.objects.annotate(
        # These names will be used when accessing them in the template for the list view
        occupied_beds_count_list=Count( # Changed name here
            Case(When(beds__patient__isnull=False, then=1), output_field=BooleanField())
        ),
        available_beds_count_list=Count( # Changed name here
            Case(When(beds__patient__isnull=True, then=1), output_field=BooleanField())
        )
    ).order_by('name')
    
    paginate_by = 10

    def test_func(self):
        return self.request.user.user_type in ['admin', 'nurse', 'receptionist']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ward List'
        return context

class WardDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Ward
    template_name = 'clinical_app/ward_detail.html'
    context_object_name = 'ward'

    def test_func(self):
        return self.request.user.user_type in ['admin', 'nurse', 'receptionist']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Ward: {self.object.name}"
        # Access the properties directly from self.object for simplicity
        context['occupied_beds_count'] = self.object.current_occupancy
        context['available_beds_count'] = self.object.available_beds_count
        # Also pass the list of beds, sorted for display
        context['beds'] = self.object.beds.all().order_by('bed_number')
        return context

class WardCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Ward
    form_class = WardForm # Use the WardForm from forms.py
    template_name = 'clinical_app/ward_form.html'
    success_url = reverse_lazy('ward_list')

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Ward '{form.instance.name}' created successfully.")
        return response

class WardUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Ward
    form_class = WardForm # Use the WardForm from forms.py
    template_name = 'clinical_app/ward_form.html'
    context_object_name = 'ward'

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def get_success_url(self):
        messages.success(self.request, f"Ward '{self.object.name}' updated successfully.")
        return reverse_lazy('ward_detail', kwargs={'pk': self.object.pk})

class WardDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Ward
    template_name = 'clinical_app/confirm_delete.html'
    context_object_name = 'object'
    success_url = reverse_lazy('ward_list')

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def form_valid(self, form):
        ward_name = self.get_object().name
        response = super().form_valid(form)
        messages.success(self.request, f"Ward '{ward_name}' deleted successfully.")
        return response


# --- Bed Views ---

class BedDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Bed
    template_name = 'clinical_app/bed_detail.html'
    context_object_name = 'bed'

    def test_func(self):
        return self.request.user.user_type in ['admin', 'nurse', 'receptionist']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Bed: {self.object.bed_number} ({self.object.ward.name})"
        return context

class BedCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Bed
    form_class = BedCreateForm # <--- Use the new BedCreateForm
    template_name = 'clinical_app/bed_form.html'

    def test_func(self):
        return self.request.user.user_type in ['admin', 'nurse']

    def dispatch(self, request, *args, **kwargs):
        self.ward = get_object_or_404(Ward, pk=kwargs['ward_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ward'] = self.ward
        context['title'] = f"Add Bed to {self.ward.name}"
        return context

    def form_valid(self, form):
        form.instance.ward = self.ward
        # is_occupied will automatically be False because patient is not set
        response = super().form_valid(form)
        messages.success(self.request, f"Bed '{form.instance.bed_number}' added to {self.ward.name} successfully.")
        return response

    def get_success_url(self):
        return reverse_lazy('ward_detail', kwargs={'pk': self.ward.pk})

class BedUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Bed
    form_class = BedUpdateForm # <--- Use the new BedUpdateForm
    template_name = 'clinical_app/bed_form.html'
    context_object_name = 'bed'

    def test_func(self):
        return self.request.user.user_type in ['admin', 'nurse']

    def get_success_url(self):
        messages.success(self.request, f"Bed '{self.object.bed_number}' updated successfully.")
        return reverse_lazy('ward_detail', kwargs={'pk': self.object.ward.pk})

# Add the AssignBedView from previous discussions here if it's not already present.
# It uses a specific BedAssignmentForm, which can be tailored for just patient assignment.
# class AssignBedView(LoginRequiredMixin, IsAdminMixin, FormView):
#     # ... (code as provided previously) ...

class BedDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Bed
    template_name = 'clinical_app/confirm_delete.html'
    context_object_name = 'object'

    def test_func(self):
        # Only admin or nurse can delete beds
        return self.request.user.user_type in ['admin', 'nurse']

    def get_success_url(self):
        ward_pk = self.object.ward.pk # Get ward_pk before deleting the bed object
        bed_info = f"{self.object.ward.name} - Bed {self.object.bed_number}"
        messages.success(self.request, f"Bed '{bed_info}' deleted successfully.")
        # log_activity(self.request.user, 'DELETE', f'Deleted Bed {bed_info}', model_name='Bed', object_id=bed_info, ip_address=get_client_ip(self.request))
        return reverse_lazy('ward_detail', kwargs={'pk': ward_pk}) # Redirect back to the ward's detail page

# --- Department List (Admin) ---

class DepartmentCreateView(LoginRequiredMixin, IsAdminMixin, CreateView):
    model = Department
    form_class = DepartmentForm # <-- Use the custom form
    template_name = 'clinical_app/department_form.html' # Reuses the form template

    def get_success_url(self):
        messages.success(self.request, f"Department '{self.object.name}' created successfully.")
        return reverse_lazy('department_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Department'
        return context

class DepartmentListView(LoginRequiredMixin, IsAdminMixin, ListView):
    model = Department
    template_name = 'clinical_app/department_list.html' # <-- This is correct!
    context_object_name = 'departments'
    ordering = ['name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Hospital Departments'
        return context

class DepartmentUpdateView(LoginRequiredMixin, IsAdminMixin, UpdateView):
    model = Department
    form_class = DepartmentForm # <-- Also use the custom form here
    template_name = 'clinical_app/department_form.html'
    context_object_name = 'department'

    def get_success_url(self):
        messages.success(self.request, f"Department '{self.object.name}' updated successfully.")
        return reverse_lazy('department_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Edit Department: {self.object.name}"
        return context

class DepartmentDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView):
    model = Department
    template_name = 'clinical_app/confirm_delete.html' # Reusable confirmation template
    context_object_name = 'object' # The object to be deleted will be available as 'object' in the template

    def get_success_url(self):
        department_name = self.get_object().name # Get the name before the object is deleted
        messages.success(self.request, f"Department '{department_name}' deleted successfully.")
        # Optionally, log activity here
        # from .utils import log_activity, get_client_ip
        # log_activity(self.request.user, 'DELETE', f'Deleted Department: {department_name}', model_name='Department', object_id=department_name, ip_address=get_client_ip(self.request))
        return reverse_lazy('department_list') # Redirect to department list after delete

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

# --- Cancer Registry Report Views ---

class CancerRegistryReportsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CancerRegistryReport
    template_name = 'clinical_app/cancer_registry_reports.html'
    context_object_name = 'reports'
    paginate_by = 20
    ordering = ['-report_date']

    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Base filter for doctors (if applicable)
        if user.user_type == 'doctor':
            if hasattr(user, 'doctor'):
                queryset = queryset.filter(patient__encounters__doctor=user.doctor).distinct()
            else:
                queryset = CancerRegistryReport.objects.none()

        # Apply filters from dashboard card links
        reported_status = self.request.GET.get('reported')
        date_range = self.request.GET.get('date_range')

        # Filter by reported status
        if reported_status is not None:
            if reported_status.lower() == 'true':
                queryset = queryset.filter(reported_to_registry=True)
            elif reported_status.lower() == 'false':
                queryset = queryset.filter(reported_to_registry=False)

        # Filter by date range
        if date_range:
            today = datetime.date.today()
            if date_range == 'last_year':
                # Filter reports from the beginning of last year to end of last year
                # Or, if you meant reports *reported* within last year's *reporting period*,
                # you might need to adjust this logic.
                # For simplicity, let's assume "from last year" means
                # from today a year ago up to today.
                # If "Last Year" meant "previous calendar year", it would be:
                # start_of_last_year = datetime.date(today.year - 1, 1, 1)
                # end_of_last_year = datetime.date(today.year - 1, 12, 31)
                # queryset = queryset.filter(report_date__range=[start_of_last_year, end_of_last_year])

                # Let's use "reports with a report_date within the last 365 days"
                # for "Last Year" to align with a common interpretation of "last X" in dashboards.
                # If you specifically meant calendar year, use the commented out logic above.
                one_year_ago = today - datetime.timedelta(days=365)
                # For 'unreported' we check `report_date`, for 'submitted' we check `registry_submission_date`
                if reported_status and reported_status.lower() == 'true':
                     queryset = queryset.filter(registry_submission_date__gte=one_year_ago)
                else: # Covers 'false' or no reported_status filter
                     queryset = queryset.filter(report_date__gte=one_year_ago)


            elif date_range == 'last_30_days':
                thirty_days_ago = today - datetime.timedelta(days=30)
                # For 'unreported' we check `report_date`, for 'submitted' we check `registry_submission_date`
                if reported_status and reported_status.lower() == 'true':
                    queryset = queryset.filter(registry_submission_date__gte=thirty_days_ago)
                else: # Covers 'false' or no reported_status filter
                    queryset = queryset.filter(report_date__gte=thirty_days_ago)


        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cancer Registry Reports'

        # Pass the active filters to the template for display or conditional rendering
        context['active_filters'] = self.request.GET.urlencode()
        context['filtered_by_reported'] = self.request.GET.get('reported')
        context['filtered_by_date_range'] = self.request.GET.get('date_range')

        return context

class CancerRegistryReportCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Handles the creation of a new Cancer Registry Report.
    Accessible to admins and doctors.
    """
    model = CancerRegistryReport
    form_class = CancerRegistryReportForm # Define this in forms.py
    template_name = 'clinical_app/cancer_registry_report_form.html' # Template for the form
    success_url = reverse_lazy('cancer_reports_list') # Redirect after successful creation

    def test_func(self):
        # Only admins and doctors can create reports
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor']

    def form_valid(self, form):
        # Automatically set patient if available from URL (if you decide to link it, not currently done)
        # Or you might want to automatically set the doctor if the user is a doctor
        if self.request.user.user_type == 'doctor' and hasattr(self.request.user, 'doctor'):
             # You might want to pre-filter diagnosis options based on the patient or doctor
             pass # Or set a field if your model had a 'created_by_doctor'
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Cancer Report'
        return context

class CancerRegistryReportDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the detailed information of a single Cancer Registry Report.
    Accessible to admins and doctors.
    """
    model = CancerRegistryReport
    template_name = 'clinical_app/cancer_registry_report_detail.html' # Template for details
    context_object_name = 'report' # How the single object will be referred to in the template

    def test_func(self):
        # Admins and Doctors can view report details
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cancer Report Details'
        return context

class CancerRegistryReportUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Handles the updating of an existing Cancer Registry Report.
    Accessible to admins and doctors.
    """
    model = CancerRegistryReport
    form_class = CancerRegistryReportForm # Reuse the same form for updating
    template_name = 'clinical_app/cancer_registry_report_form.html' # Reuse the form template
    success_url = reverse_lazy('cancer_reports_list') # Redirect after update

    def test_func(self):
        # Admins and Doctors can update reports
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'doctor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Cancer Report'
        return context

class CancerRegistryReportDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Handles the deletion of a Cancer Registry Report.
    Typically restricted to administrators for data integrity.
    """
    model = CancerRegistryReport
    template_name = 'clinical_app/cancer_registry_report_confirm_delete.html' # Template for delete confirmation
    success_url = reverse_lazy('cancer_reports_list') # Redirect after deletion

    def test_func(self):
        # Only admin can delete reports
        return self.request.user.is_authenticated and \
               self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Cancer Report'
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

class BirthRecordCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = BirthRecord
    form_class = BirthRecordForm # Create a forms.py and define BirthRecordForm
    template_name = 'clinical_app/birth_record_form.html' # Create this template
    success_url = reverse_lazy('birth_records_list') # Redirect to list after creation

    def test_func(self):
        # Only admin, receptionists, nurses can create birth records
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Birth Record'
        return context

class BirthRecordDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = BirthRecord
    template_name = 'clinical_app/birth_record_detail.html' # Create this template
    context_object_name = 'record'

    def test_func(self):
        # Any authenticated user with relevant roles can view details
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse', 'doctor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Birth Record Details'
        return context

class BirthRecordUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = BirthRecord
    form_class = BirthRecordForm # Use the same form for update
    template_name = 'clinical_app/birth_record_form.html' # Reuse the form template
    success_url = reverse_lazy('birth_records_list') # Redirect to list after update

    def test_func(self):
        # Only admin, receptionists, nurses can update birth records
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Birth Record'
        return context

class BirthRecordDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = BirthRecord
    template_name = 'clinical_app/birth_record_confirm_delete.html' # Create this template for confirmation
    success_url = reverse_lazy('birth_records_list') # Redirect to list after deletion

    def test_func(self):
        # Only admin can delete birth records (or adjust as per your policy)
        return self.request.user.is_authenticated and \
               self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Birth Record'
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

class MortalityRecordCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Handles the creation of a new Mortality Record.
    Accessible to admins, receptionists, and nurses for data entry.
    """
    model = MortalityRecord
    form_class = MortalityRecordForm  # The form defined in forms.py
    template_name = 'clinical_app/mortality_record_form.html'  # Path to your form template
    success_url = reverse_lazy('mortality_records_list')  # Redirect after successful creation

    def test_func(self):
        """
        Defines which user types are allowed to create mortality records.
        """
        # Admins, Receptionists, Nurses are common for data entry
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse']

    def get_context_data(self, **kwargs):
        """
        Adds extra context data to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Mortality Record'
        return context

class MortalityRecordDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Displays the detailed information of a single Mortality Record.
    Accessible to admins, receptionists, doctors, and nurses.
    """
    model = MortalityRecord
    template_name = 'clinical_app/mortality_record_detail.html'  # Path to your detail template
    context_object_name = 'record'  # How the single object will be referred to in the template

    def test_func(self):
        """
        Defines which user types are allowed to view mortality record details.
        """
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'doctor', 'nurse']

    def get_context_data(self, **kwargs):
        """
        Adds extra context data to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Mortality Record Details'
        return context

class MortalityRecordUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Handles the updating of an existing Mortality Record.
    Accessible to admins, receptionists, and nurses.
    """
    model = MortalityRecord
    form_class = MortalityRecordForm  # Reuse the same form for updating
    template_name = 'clinical_app/mortality_record_form.html'  # Reuse the form template
    success_url = reverse_lazy('mortality_records_list')  # Redirect after successful update

    def test_func(self):
        """
        Defines which user types are allowed to update mortality records.
        """
        return self.request.user.is_authenticated and \
               self.request.user.user_type in ['admin', 'receptionist', 'nurse']

    def get_context_data(self, **kwargs):
        """
        Adds extra context data to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Mortality Record'
        return context

class MortalityRecordDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Handles the deletion of a Mortality Record.
    Typically restricted to administrators for data integrity.
    """
    model = MortalityRecord
    template_name = 'clinical_app/mortality_record_confirm_delete.html'  # Path to your delete confirmation template
    success_url = reverse_lazy('mortality_records_list')  # Redirect after successful deletion

    def test_func(self):
        """
        Defines which user types are allowed to delete mortality records.
        """
        # Deletion is often restricted to administrators for data integrity
        return self.request.user.is_authenticated and \
               self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        """
        Adds extra context data to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Delete Mortality Record'
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