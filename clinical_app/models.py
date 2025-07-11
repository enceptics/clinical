from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date, timedelta # Import timedelta for date calculations
import uuid
from django.urls import reverse # Import reverse for get_absolute_url
from decimal import Decimal, InvalidOperation, DivisionByZero,ROUND_HALF_UP
from django.utils import timezone 

# -----------------------------------------------------------------------------
# User and Staff Management (Custom User Model)
# -----------------------------------------------------------------------------

SHIFT_CHOICES = [
        ('Morning', 'Morning Shift'),
        ('Afternoon', 'Afternoon Shift'),
        ('Full Day', 'Full Day Shift'),
        ('Night', 'Night Shift'),
    ]
STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('On Leave', 'On Leave'),
    ]
status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Active',
        help_text="Current employment status of the receptionist."
    )

class User(AbstractUser):
    """
    Custom User model to extend Django's default User.
    This allows us to add specific roles like Doctor, Nurse, Admin, etc.
    """
    USER_TYPE_CHOICES = (
        ('admin', 'Administrator'),
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('pharmacist', 'Pharmacist'),
        ('lab_tech', 'Lab Technician'),
        ('radiologist', 'Radiologist'),
        ('patient', 'Patient'),
        ('receptionist', 'Receptionist'),
        ('procurement_officer', 'Procurement Officer'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='patient')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender_choices = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    gender = models.CharField(max_length=10, choices=gender_choices, blank=True, null=True)

    # Add these lines to resolve the clash
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=('groups'),
        blank=True,
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="clinical_app_user_set", # Changed this line
        related_query_name="clinical_app_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=('user permissions'),
        blank=True,
        help_text=('Specific permissions for this user.'),
        related_name="clinical_app_user_permissions_set", # Changed this line
        related_query_name="clinical_app_user",
    )

    def __str__(self):
        return self.username

class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'View'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('OTHER', 'Other'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             help_text="User who performed the action (can be null if system action)")
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES,
                                   help_text="Type of action performed")
    timestamp = models.DateTimeField(auto_now_add=True,
                                     help_text="When the action occurred")
    ip_address = models.GenericIPAddressField(null=True, blank=True,
                                             help_text="IP address of the user")
    model_name = models.CharField(max_length=100, blank=True, null=True,
                                  help_text="Name of the model affected (e.g., 'Patient', 'Doctor')")
    object_id = models.CharField(max_length=255, blank=True, null=True,
                                 help_text="ID of the object affected")
    description = models.TextField(blank=True,
                                   help_text="Detailed description of the action")
    changes = models.JSONField(null=True, blank=True,
                               help_text="JSON representation of changes (e.g., {'field': 'old_value' -> 'new_value'})")

    class Meta:
        ordering = ['-timestamp'] # Order by newest first
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"

    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {self.user or 'System'} - {self.action_type} on {self.model_name or 'N/A'} (ID: {self.object_id or 'N/A'})"


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'user_type': 'doctor'})
    specialization = models.CharField(max_length=100)
    medical_license_number = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    years_of_experience = models.IntegerField(default=0, null=True, blank=True, help_text="Years of experience as a doctor.")

    # Add more doctor-specific fields like availability, schedule, etc.

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} ({self.specialization})"

class Nurse(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'user_type': 'nurse'})
    nursing_license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    # Add nurse-specific fields if any

    def __str__(self):
        return f"Nurse {self.user.first_name} {self.user.last_name}"

class Pharmacist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'user_type': 'pharmacist'})
    pharmacy_license_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    years_of_experience = models.IntegerField(default=0, help_text="Years of experience in pharmacy.")
    # Add other relevant fields for a Pharmacist here, e.g.:
    # registered_date = models.DateField(auto_now_add=True)
    # specialized_area = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Pharmacist {self.user.first_name} {self.user.last_name}"

class ProcurementOfficer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'user_type': 'procurement_officer'})
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    # You might want to link to a 'Department' model specifically for this role if it's different
    # from the general user's department, or if you need to track their specific procurement department.
    # department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Procurement Officer {self.user.first_name} {self.user.last_name}"

class Department(models.Model):
    CLINICAL = 'Clinical'
    ADMINISTRATIVE = 'Administrative'
    DIAGNOSTIC = 'Diagnostic'
    SUPPORT = 'Support'
    EMERGENCY = 'Emergency'
    SURGICAL = 'Surgical'
    DEPARTMENT_TYPE_CHOICES = [
        (CLINICAL, 'Clinical Services'),
        (ADMINISTRATIVE, 'Administrative Services'),
        (DIAGNOSTIC, 'Diagnostic Services'),
        (SUPPORT, 'Support Services'),
        (EMERGENCY, 'Emergency Services'),
        (SURGICAL, 'Surgical Services'),
    ]

    name = models.CharField(max_length=100, unique=True,
                            help_text="The official name of the department (e.g., 'Pediatrics', 'Radiology').")
    description = models.TextField(blank=True, null=True,
                                   help_text="A brief overview of the department's functions and scope.")

    # --- Operational & Contact Information ---
    department_type = models.CharField(max_length=50, choices=DEPARTMENT_TYPE_CHOICES, default=CLINICAL,
                                       help_text="Category of the department (e.g., Clinical, Administrative).")

    # Assuming 'User' model includes doctors/heads; adjust if you have a separate 'Doctor' model.
    head_of_department = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='departments_headed',
                                           help_text="The lead or head of this department.")

    contact_phone = models.CharField(max_length=20, blank=True, null=True,
                                     help_text="Primary phone number for direct departmental contact.")
    contact_email = models.EmailField(max_length=254, blank=True, null=True,
                                      help_text="Primary email address for the department.")

    # --- Location Information ---
    location = models.CharField(max_length=255, blank=True, null=True,
                                help_text="Physical location within the hospital (e.g., 'Ground Floor, East Wing', 'Building C, Level 2').")
    
    floor_number = models.IntegerField(blank=True, null=True,
                                       help_text="The floor number where the department is located.")

    staff_count = models.IntegerField(blank=True, null=True,
                                      help_text="Approximate total number of staff members in the department.")

    annual_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,
                                        help_text="The allocated annual budget for this department. Useful for procurement tracking.")
 
    is_active = models.BooleanField(default=True,
                                    help_text="Designates whether this department is currently operational and active.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ['name'] 

    def __str__(self):
        return self.name

    def get_absolute_url(self):

        from django.urls import reverse
        return reverse('department_list')


# -----------------------------------------------------------------------------
# Patient Management
# -----------------------------------------------------------------------------

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'user_type': 'patient'})
    patient_id = models.CharField(max_length=20, unique=True, editable=False) # Auto-generated patient ID
    blood_group_choices = (
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    )
    blood_group = models.CharField(max_length=5, choices=blood_group_choices, blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=20)
    allergies = models.TextField(blank=True, null=True, help_text="List known allergies (e.g., medications, food)")
    pre_existing_conditions = models.TextField(blank=True, null=True, help_text="List any chronic conditions")
    registration_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.patient_id:
            # Generate a unique patient ID (e.g., based on timestamp or UUID)
            self.patient_id = f"PAT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Returns the URL to access a particular instance of Patient."""
        return reverse('patient_detail', args=[str(self.pk)]) # Assumes 'patient_detail' URL name

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.patient_id})"

class ConsentForm(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consent_forms')
    consent_type = models.CharField(max_length=100) # e.g., "General Treatment Consent", "Surgical Consent", "Data Sharing Consent"
    consent_text = models.TextField()
    is_signed = models.BooleanField(default=False)
    signed_date = models.DateTimeField(null=True, blank=True)
    # For digital signature, you might store a hash, an image, or integrate with a digital signature service
    digital_signature_hash = models.CharField(max_length=255, blank=True, null=True)
    signed_by_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='consents_obtained')
    document_file = models.FileField(upload_to='consent_forms/', blank=True, null=True) # To upload scanned copies

    def __str__(self):
        return f"{self.consent_type} for {self.patient}"

# -----------------------------------------------------------------------------
# Receptionist, Radiologist, Lab Technitian, Bed Management
# -----------------------------------------------------------------------------
class Receptionist(models.Model):
    """
    Model representing a Receptionist in the healthcare system.
    Handles front-office tasks, appointments, etc.
    """
    # Link to the custom User model.
    # The primary_key=True makes the 'user_id' also the primary key of the Receptionist table.
    # Corrected limit_choices_to to 'receptionist' as per your User model's choices.
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        limit_choices_to={'user_type': 'receptionist'} # Corrected user_type
    )

    # Choices for shift information (optional, but good practice for limited options)
    SHIFT_CHOICES = [
        ('Morning', 'Morning Shift'),
        ('Afternoon', 'Afternoon Shift'),
        ('Full Day', 'Full Day Shift'),
        ('Night', 'Night Shift'),
    ]
    shift_info = models.CharField(
        max_length=50,
        choices=SHIFT_CHOICES,
        blank=True,
        null=True,
        help_text="Information about the receptionist's working shift."
    )

    assigned_desk = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="The desk or area they are typically assigned to."
    )

    class Meta:
        verbose_name = "Receptionist"
        verbose_name_plural = "Receptionists"
        # Order by user's last name then first name
        ordering = ['user__last_name', 'user__first_name']


    def __str__(self):
        # Access user attributes directly via the 'user' relationship
        return f"{self.user.first_name} {self.user.last_name} (Username: {self.user.username})"

class LabTechnician(models.Model):
    """
    Model representing a Lab Technician in the healthcare system.
    Responsible for performing lab tests and analyses.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        limit_choices_to={'user_type': 'lab_tech'} # Corrected user_type to 'lab_tech'
    )

    license_number = models.CharField(
        max_length=50,
        unique=True,
        null=False,
        blank=False,
        help_text="Professional license number for the lab technician."
    )

    SPECIALIZATION_CHOICES = [
        ('Phlebotomy', 'Phlebotomy'),
        ('Microbiology', 'Microbiology'),
        ('Clinical Chemistry', 'Clinical Chemistry'),
        ('Hematology', 'Hematology'),
        ('Pathology', 'Pathology'),
        ('Virology', 'Virology'),
        ('Molecular Biology', 'Molecular Biology'),
        ('Other', 'Other'),
    ]
    specialization = models.CharField(
        max_length=100,
        choices=SPECIALIZATION_CHOICES,
        blank=True,
        null=True,
        help_text="Area of expertise or specialization."
    )

    shift_info = models.CharField(
        max_length=50,
        choices=SHIFT_CHOICES, # Using global SHIFT_CHOICES
        blank=True,
        null=True
    )
    lab_section_assigned = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The specific lab section they primarily work in."
    )
    qualifications = models.TextField(
        blank=True,
        null=True,
        help_text="Educational background, certifications, and other qualifications."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES, # Using global STATUS_CHOICES
        default='Active',
        help_text="Current employment status of the lab technician."
    )

    class Meta:
        verbose_name = "Lab Technician"
        verbose_name_plural = "Lab Technicians"
        ordering = ['user__last_name', 'user__first_name'] # Corrected ordering to use user fields

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} (License: {self.license_number})"


class Radiologist(models.Model):
    """
    Model representing a Radiologist in the healthcare system.
    A medical doctor specializing in interpreting medical images.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        limit_choices_to={'user_type': 'radiologist'} # Corrected user_type to 'radiologist'
    )
    # radiologist_id is removed as user.pk serves as the primary key

    medical_license_number = models.CharField(
        max_length=50,
        unique=True,
        null=False,
        blank=False,
        help_text="Medical license number for the radiologist."
    )

    SUB_SPECIALIZATION_CHOICES = [
        ('Diagnostic Radiology', 'Diagnostic Radiology'),
        ('Interventional Radiology', 'Interventional Radiology'),
        ('Pediatric Radiology', 'Pediatric Radiology'),
        ('Neuroradiology', 'Neuroradiology'),
        ('Musculoskeletal Radiology', 'Musculoskeletal Radiology'),
        ('Cardiothoracic Radiology', 'Cardiothoracic Radiology'),
        ('Breast Imaging', 'Breast Imaging'),
        ('Nuclear Medicine', 'Nuclear Medicine'),
        ('Other', 'Other'),
    ]
    sub_specialization = models.CharField(
        max_length=100,
        choices=SUB_SPECIALIZATION_CHOICES,
        blank=True,
        null=True,
        help_text="Specific area of radiology expertise (e.g., Neuroradiology)."
    )

    # Date hired is specific to the role, distinct from date_of_birth on User
    date_hired = models.DateField(null=False, blank=False)
    on_call_status = models.BooleanField(
        default=False,
        help_text="Indicates if the radiologist is currently on-call."
    )

    # Using JSONField for preferred_modalities (requires PostgreSQL or custom handling)
    preferred_modalities = models.JSONField(
        blank=True,
        null=True,
        help_text="List of preferred imaging modalities (e.g., ['MRI', 'CT', 'X-ray']).",
    )

    qualifications = models.TextField(
        blank=True,
        null=True,
        help_text="Medical degrees, board certifications, and other qualifications."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES, # Using global STATUS_CHOICES
        default='Active',
        help_text="Current employment status of the radiologist."
    )

    class Meta:
        verbose_name = "Radiologist"
        verbose_name_plural = "Radiologists"
        ordering = ['user__last_name', 'user__first_name'] # Corrected ordering to use user fields

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} ({self.sub_specialization or 'Radiologist'})"

# -----------------------------------------------------------------------------
# Clinical Consultations & Records
# -----------------------------------------------------------------------------

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateTimeField(null=True, blank=True)
    appointment_time = models.DateTimeField(null=True, blank=True)
    reason_for_visit = models.TextField()
    status_choices = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
        ('no_show', 'No Show'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-appointment_date']

    def __str__(self):
        return f"Appointment for {self.patient} with {self.doctor} on {self.appointment_date.strftime('%Y-%m-%d %H:%M')}"

class Encounter(models.Model):
    """
    Represents a single patient visit or interaction with the healthcare system.
    This can be linked to an appointment or be an unscheduled visit (e.g., emergency).
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='encounters')
    appointment = models.OneToOneField(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='encounter')
    encounter_date = models.DateTimeField(auto_now_add=True)
    encounter_type_choices = (
        ('outpatient', 'Outpatient'),
        ('inpatient', 'Inpatient'),
        ('emergency', 'Emergency'),
        ('telemedicine', 'Telemedicine'),
    )
    encounter_type = models.CharField(max_length=20, choices=encounter_type_choices, default='outpatient')
    # For inpatient: admission_date, discharge_date, ward, bed_number, etc.
    admission_date = models.DateTimeField(null=True, blank=True)
    discharge_date = models.DateTimeField(null=True, blank=True)
    ward = models.ForeignKey('Ward', on_delete=models.SET_NULL, null=True, blank=True)
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"Encounter for {self.patient} on {self.encounter_date.strftime('%Y-%m-%d')}"


class VitalSign(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='vital_signs')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Nurse or Doctor
    timestamp = models.DateTimeField(auto_now_add=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="in Celsius")
    blood_pressure_systolic = models.IntegerField(null=True, blank=True, help_text="Systolic BP (mmHg)")
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True, help_text="Diastolic BP (mmHg)")
    heart_rate = models.IntegerField(null=True, blank=True, help_text="BPM")
    respiratory_rate = models.IntegerField(null=True, blank=True, help_text="Breaths per minute")
    oxygen_saturation = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="%")
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Weight in KG")
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Height in CM")
    bmi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Calculated field

    def __str__(self):
        return f"Vitals for {self.encounter.patient} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if self.weight_kg is None or self.height_cm is None:
            self.bmi = None
        else:
            try:
                weight = Decimal(self.weight_kg)
                height = Decimal(self.height_cm) / Decimal('100')
                if height > 0:
                    bmi = weight / (height ** 2)
                    bmi = bmi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if bmi < Decimal('1000'):
                        self.bmi = bmi
                    else:
                        self.bmi = None
                else:
                    self.bmi = None
            except (InvalidOperation, TypeError):
                self.bmi = None

        super().save(*args, **kwargs)


class MedicalHistory(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_history_entries')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_history_recorded_by_set')
    recorded_date = models.DateTimeField(auto_now_add=True)
    chief_complaint = models.TextField(blank=True, null=True)
    history_of_present_illness = models.TextField(blank=True, null=True)
    past_medical_history = models.TextField(blank=True, null=True)
    surgical_history = models.TextField(blank=True, null=True)
    family_history = models.TextField(blank=True, null=True)
    social_history = models.TextField(blank=True, null=True)
    medication_history = models.TextField(blank=True, null=True) # Can be a separate Medication model

    def __str__(self):
        return f"Medical History for {self.patient} on {self.recorded_date.strftime('%Y-%m-%d')}"

class PhysicalExamination(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='physical_examinations')
    examined_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='physical_examinations_examined_by_set')
    examination_date = models.DateTimeField(auto_now_add=True)
    general_appearance = models.TextField(blank=True, null=True)
    head_and_neck = models.TextField(blank=True, null=True)
    chest_and_lungs = models.TextField(blank=True, null=True)
    heart_and_circulation = models.TextField(blank=True, null=True)
    abdomen = models.TextField(blank=True, null=True)
    musculoskeletal = models.TextField(blank=True, null=True)
    neurological = models.TextField(blank=True, null=True)
    skin = models.TextField(blank=True, null=True)
    other_findings = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Physical Exam for {self.encounter.patient} on {self.examination_date.strftime('%Y-%m-%d')}"

# In your models.py file, within the Diagnosis class

class Diagnosis(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='diagnoses')
    diagnosed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='diagnoses_made_by_set')
    diagnosis_date = models.DateTimeField(auto_now_add=True)
    icd10_code = models.CharField(max_length=20, blank=True, null=True) # International Classification of Diseases
    diagnosis_text = models.TextField()
    is_primary = models.BooleanField(default=False) # Is this the main diagnosis for the encounter?

    # --- ADD THIS NEW FIELD ---
    DIAGNOSIS_STATUS_CHOICES = (
        ('provisional', 'Provisional'),
        ('final', 'Final'),
        ('differential', 'Differential'),
        ('ruled_out', 'Ruled Out'),
        ('resolved', 'Resolved'), # Added resolved as per your comment
    )
    diagnosis_status = models.CharField(
        max_length=20, # Ensure this is long enough for your longest choice value
        choices=DIAGNOSIS_STATUS_CHOICES,
        default='provisional', # Set a sensible default
        help_text="Current status of the diagnosis (e.g., provisional, final)."
    )
    # --- END NEW FIELD ---

    class Meta:
        verbose_name_plural = "Diagnoses"

    def __str__(self):
        return f"{self.diagnosis_text} ({self.icd10_code if self.icd10_code else 'No Code'})"

class TreatmentPlan(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='treatment_plans')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='treatment_plans_created_by_set')
    created_date = models.DateTimeField(auto_now_add=True)
    treatment_description = models.TextField()
    recommendations = models.TextField(blank=True, null=True)
    expected_return_date = models.DateField(null=True, blank=True)
    status_choices = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('discontinued', 'Discontinued'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='active')

    def __str__(self):
        return f"Treatment Plan for {self.encounter.patient} on {self.created_date.strftime('%Y-%m-%d')}"

# -----------------------------------------------------------------------------
# What has been done to the patient
# -----------------------------------------------------------------------------

class ClinicalNote(models.Model):
    """
    Records detailed clinical information for a specific encounter.
    This covers what was done, observed, and planned during a patient visit.
    """
    encounter = models.OneToOneField(
        'Encounter',
        on_delete=models.CASCADE,
        related_name='clinical_note',
        help_text="The encounter this clinical note is associated with."
    )
    chief_complaint = models.TextField(
        verbose_name="Chief Complaint",
        help_text="Patient's primary reason for the visit (in their own words if possible)."
    )
    history_of_present_illness = models.TextField(
        blank=True,
        null=True,
        verbose_name="History of Present Illness (HPI)",
        help_text="Detailed chronological description of the chief complaint."
    )
    review_of_systems = models.TextField(
        blank=True,
        null=True,
        verbose_name="Review of Systems (ROS)",
        help_text="Systematic inquiry about symptoms in different body systems."
    )
    physical_exam_findings = models.TextField(
        blank=True,
        null=True,
        verbose_name="Physical Examination Findings",
        help_text="Objective findings from the physical exam."
    )
    assessment = models.TextField(
        verbose_name="Assessment",
        help_text="Provider's medical impression and differential diagnoses."
    )
    plan = models.TextField(
        verbose_name="Plan",
        help_text="Proposed diagnostic, therapeutic, and management strategies."
    )
    # You might link to a separate Diagnosis model if you have one, or just store text
    # diagnosis = models.ForeignKey(Diagnosis, on_delete=models.SET_NULL, null=True, blank=True)
    # For now, let's keep it simple with text.
    primary_diagnosis = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Primary Diagnosis (e.g., ICD-10 code and description)"
    )
    secondary_diagnoses = models.TextField(
        blank=True,
        null=True,
        verbose_name="Secondary Diagnoses",
        help_text="Comma-separated list of additional diagnoses."
    )
    # Interventions, Procedures, Medications could be free text or separate models
    interventions_performed = models.TextField(
        blank=True,
        null=True,
        verbose_name="Interventions/Procedures Performed",
        help_text="Details of any procedures, therapies, or specific interventions carried out."
    )
    medications_prescribed = models.TextField(
        blank=True,
        null=True,
        verbose_name="Medications Prescribed/Administered",
        help_text="List of medications, dosage, frequency, and route."
    )
    follow_up_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name="Follow-up Instructions",
        help_text="Instructions given to the patient for follow-up care."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_clinical_notes',
        help_text="The user who created this note."
    )

    class Meta:
        verbose_name = "Clinical Note"
        verbose_name_plural = "Clinical Notes"
        ordering = ['-created_at']

    def __str__(self):
        return f"Clinical Note for {self.encounter.patient.user.get_full_name()} on {self.encounter.encounter_date.strftime('%Y-%m-%d')}"

# -----------------------------------------------------------------------------
# Investigations (Lab & Imaging)
# -----------------------------------------------------------------------------

class LabTestCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Lab Test Categories"

    def __str__(self):
        return self.name

class LabTest(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(LabTestCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tests')
    unit = models.CharField(max_length=20, blank=True, null=True) # e.g., "mg/dL", "mmol/L"
    normal_range = models.CharField(max_length=50, blank=True, null=True) # e.g., "70-100 mg/dL"
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # For billing integration

    def __str__(self):
        return self.name

class LabTestRequest(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='lab_test_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_test_requests_made_by_set')
    requested_date = models.DateTimeField(auto_now_add=True)
    tests = models.ManyToManyField(LabTest)
    request_notes = models.TextField(blank=True, null=True)
    status_choices = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='pending')

    def __str__(self):
        return f"Lab request for {self.encounter.patient} on {self.requested_date.strftime('%Y-%m-%d')}"

    # Add this method to get a display string for the associated tests
    def get_tests_display(self):
        return ", ".join([test.name for test in self.tests.all()])

    def get_status_badge_class(self):
        """Returns the Bootstrap badge class and appropriate text color for the current status."""
        if self.status == 'completed':
            return 'badge-success text-white' # Green background, white text
        elif self.status == 'pending':
            return 'badge-warning text-dark'  # Yellow background, dark text
        elif self.status == 'in_progress':
            return 'badge-primary text-white' # Blue background, white text
        elif self.status == 'cancelled':
            return 'badge-danger text-white'  # Red background, white text
        else: # Fallback for any unexpected status
            return 'badge-info text-dark'     # Light blue background, dark text

class LabTestResult(models.Model):
    request = models.ForeignKey(LabTestRequest, on_delete=models.CASCADE, related_name='results')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    result_value = models.CharField(max_length=255, blank=True, null=True) # Can be numerical or text
    result_unit = models.CharField(max_length=20, blank=True, null=True) # Unit of the result
    normal_range_at_time_of_test = models.CharField(max_length=50, blank=True, null=True) # Store for reference
    is_abnormal = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_test_results_performed_by_set')
    result_date = models.DateTimeField(auto_now_add=True)
    result_file = models.FileField(upload_to='lab_results/', blank=True, null=True) # For scanned reports

    def __str__(self):
        return f"Result for {self.test.name} for {self.request.encounter.patient}"

    # Add this method to get a display string for the associated tests
    def get_tests_display(self):
        return ", ".join([test.name for test in self.tests.all()])

class ImagingType(models.Model):
    name = models.CharField(max_length=100, unique=True) # e.g., "X-Ray", "CT Scan", "MRI", "Ultrasound"
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # For billing integration

    def __str__(self):
        return self.name

class ImagingRequest(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='imaging_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='imaging_requests_made_by_set')
    requested_date = models.DateTimeField(auto_now_add=True)
    imaging_type = models.ForeignKey(ImagingType, on_delete=models.CASCADE)
    reason_for_exam = models.TextField()
    body_part = models.CharField(max_length=100, blank=True, null=True)
    status_choices = (
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('performed', 'Performed'),
        ('reported', 'Reported'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='pending')

    def __str__(self):
        return f"Imaging request for {self.encounter.patient} ({self.imaging_type.name})"

class ImagingResult(models.Model):
    request = models.OneToOneField(ImagingRequest, on_delete=models.CASCADE, related_name='result')
    radiologist = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='imaging_results_reported_by_set')
    report_date = models.DateTimeField(default=timezone.now) # Changed
    findings = models.TextField()
    impression = models.TextField()
    recommendations = models.TextField(blank=True, null=True)
    image_files = models.FileField(upload_to='imaging_results/', blank=True, null=True)

    def __str__(self):
        return f"Imaging Report for {self.request.encounter.patient} ({self.request.imaging_type.name})"

# -----------------------------------------------------------------------------
# Pharmacy & Medication Management
# -----------------------------------------------------------------------------

class Medication(models.Model):
    name = models.CharField(max_length=255, unique=True)
    strength = models.CharField(max_length=50, blank=True, null=True) # e.g., "500mg", "10mg/mL"
    form = models.CharField(max_length=50, blank=True, null=True) # e.g., "Tablet", "Syrup", "Injection"
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # New fields for stock management
    stock_quantity = models.IntegerField(default=0, help_text="Current quantity in stock")
    reorder_level = models.IntegerField(default=10, help_text="Minimum quantity to trigger reorder")

    def __str__(self):
        return f"{self.name} {self.strength}"

class Prescription(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='prescriptions')
    prescribed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions_prescribed_by_set')
    prescription_date = models.DateTimeField(auto_now_add=True)
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE)
    dosage = models.CharField(max_length=100) # e.g., "1 tablet", "5 mL"
    frequency = models.CharField(max_length=100) # e.g., "Twice daily", "Every 8 hours"
    duration = models.CharField(max_length=100) # e.g., "7 days", "Until finished"
    route = models.CharField(max_length=50, blank=True, null=True) # e.g., "Oral", "IV", "Topical"
    notes = models.TextField(blank=True, null=True)
    is_dispensed = models.BooleanField(default=False)
    dispensed_by = models.ForeignKey(Pharmacist, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions_dispensed')
    dispensed_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Prescription for {self.medication.name} to {self.encounter.patient}"

# -----------------------------------------------------------------------------
# Inpatient Management (Ward & Bed)
# -----------------------------------------------------------------------------

class Ward(models.Model):
    name = models.CharField(max_length=100, unique=True)
    ward_type_choices = (
        ('general', 'General'),
        ('private', 'Private'),
        ('icu', 'Intensive Care Unit'),
        ('maternity', 'Maternity'),
        ('pediatric', 'Pediatric'),
        ('oncology', 'Oncology'),
    )
    ward_type = models.CharField(max_length=50, choices=ward_type_choices, default='general')
    capacity = models.IntegerField()

    def __str__(self):
        return self.name

    @property
    def current_occupancy(self):
        """Calculates the number of currently occupied beds in this ward."""
        # This filters related beds where the 'patient' field is NOT NULL
        return self.beds.filter(patient__isnull=False).count()

    @property
    def available_beds_count(self):
        """Calculates the number of available (unoccupied) beds in this ward."""
        # This filters related beds where the 'patient' field IS NULL
        return self.beds.filter(patient__isnull=True).count()

class Bed(models.Model):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=20)
    # The `is_occupied` field becomes redundant if `patient` is present.
    # We can remove it and use a property, or keep it and update it via save/forms.
    # For now, let's keep it but rely on the patient field.
    is_occupied = models.BooleanField(default=False) # Will be updated by save method or form

    # Add the foreign key to Patient
    patient = models.OneToOneField(
        'Patient',            # 'Patient' as string if Patient is defined later in the file
        on_delete=models.SET_NULL, # When a patient record is deleted, set this bed's patient to NULL
        null=True,             # A bed can be empty
        blank=True,            # Allow empty in forms
        related_name='current_bed', # Allows patient.current_bed to get the bed object
        help_text="The patient currently assigned to this bed. Null if bed is empty."
    )

    class Meta:
        unique_together = ('ward', 'bed_number')

    def __str__(self):
        status = "Occupied" if self.patient else "Available"
        patient_name = f" ({self.patient.get_full_name()})" if self.patient and hasattr(self.patient, 'get_full_name') else ""
        return f"{self.ward.name} - Bed {self.bed_number} ({status}{patient_name})"

    # Optional: Override save method to keep is_occupied in sync
    def save(self, *args, **kwargs):
        self.is_occupied = self.patient is not None
        super().save(*args, **kwargs)

# -----------------------------------------------------------------------------
# Case Summary & Reporting
# -----------------------------------------------------------------------------

class CaseSummary(models.Model):
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE, related_name='case_summary')
    summary_text = models.TextField() # Consolidated summary
    prepared_by = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    summary_date = models.DateTimeField(auto_now_add=True)
    digital_signature_hash = models.CharField(max_length=255, blank=True, null=True) # Doctor's digital signature

    # Fields for the electronic signature
    signed_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_clinical_summaries')
    user_signature_image = models.ImageField(upload_to='signatures/case_summaries/', null=True, blank=True)
    user_initials = models.CharField(max_length=10, blank=True, null=True)
    is_signed = models.BooleanField(default=False)
    date_signed = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Case Summaries"

    def __str__(self):
        return f"Case Summary for {self.encounter.patient} on {self.summary_date.strftime('%Y-%m-%d')}"

# -----------------------------------------------------------------------------
# Oncology Specific Reporting (Kenya National Cancer Registry)
# -----------------------------------------------------------------------------

class CancerRegistryReport(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='cancer_registry_reports')
    diagnosis = models.ForeignKey(Diagnosis, on_delete=models.SET_NULL, null=True, blank=True, help_text="Link to the specific cancer diagnosis")
    report_date = models.DateField(default=date.today)
    cancer_type = models.CharField(max_length=255)
    stage = models.CharField(max_length=50, blank=True, null=True)
    treatment_modalities = models.TextField(blank=True, null=True, help_text="e.g., Surgery, Chemotherapy, Radiotherapy")
    date_of_diagnosis = models.DateField(blank=True, null=True)
    date_of_last_follow_up = models.DateField(blank=True, null=True)
    vital_status_choices = (
        ('alive', 'Alive'),
        ('dead', 'Dead'),
    )
    vital_status = models.CharField(max_length=10, choices=vital_status_choices, default='alive')
    date_of_death = models.DateField(null=True, blank=True)
    cause_of_death = models.TextField(blank=True, null=True)
    reported_to_registry = models.BooleanField(default=False)
    registry_submission_date = models.DateTimeField(null=True, blank=True)
    # Specific fields for Kenya National Cancer Registry based on their requirements
    # e.g., KCR_ID, specific demographic fields, occupation, etc.

    class Meta:
        verbose_name_plural = "Cancer Registry Reports"
        unique_together = ('patient', 'diagnosis', 'report_date') # Avoid duplicate reports for same patient/diagnosis/day

    def __str__(self):
        return f"Cancer Report for {self.patient} - {self.cancer_type} on {self.report_date}"

# You might also have a separate model for `BirthRecord` and `MortalityRecord`
# if "Number of children born, number of mortality etc" refers to
# general hospital statistics rather than directly within the oncology context.

class BirthRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='birth_records', help_text="Link to the mother's patient record")
    baby_name = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateTimeField()
    gender = models.CharField(max_length=10, choices=User.gender_choices)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    apgar_score_1min = models.IntegerField(null=True, blank=True)
    apgar_score_5min = models.IntegerField(null=True, blank=True)
    mode_of_delivery = models.CharField(max_length=50, blank=True, null=True)
    delivered_by = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    delivery_notes = models.TextField(blank=True, null=True)
    is_multiple_birth = models.BooleanField(default=False)
    # If twins/triplets, link to other babies or a 'Delivery' event.
    # Add fields for birth complications,

    def __str__(self):
        return f"Birth Record for {self.baby_name or 'Baby of ' + self.patient.user.get_full_name()} on {self.date_of_birth.strftime('%Y-%m-%d')}"

class MortalityRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='mortality_records', null=True, blank=True)
    # If patient is not known or for external deaths recorded by hospital
    full_name = models.CharField(max_length=255, blank=True, null=True, help_text="Full name if patient record not linked")
    date_of_death = models.DateTimeField()
    cause_of_death = models.TextField(help_text="Primary cause of death")
    contributing_factors = models.TextField(blank=True, null=True)
    death_location_choices = (
        ('ward', 'In-patient Ward'),
        ('icu', 'ICU'),
        ('er', 'Emergency Room'),
        ('other', 'Other (specify)'),
    )
    death_location = models.CharField(max_length=50, choices=death_location_choices, blank=True, null=True)
    # You might link to an encounter if the death occurred during an active encounter
    encounter = models.OneToOneField(Encounter, on_delete=models.SET_NULL, null=True, blank=True, help_text="Encounter during which death occurred")
    certified_by = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    certificate_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    reported_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        name = self.patient.user.get_full_name() if self.patient else self.full_name
        return f"Mortality Record for {name} on {self.date_of_death.strftime('%Y-%m-%d')}"