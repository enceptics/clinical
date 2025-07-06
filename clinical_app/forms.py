# clinical_app/forms.py
from django import forms
import string
import secrets
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.db.models import Max # Import Max for auto-incrementing IDs
from django.core.exceptions import ValidationError
import secrets # For generating secure temporary passwords
import string # For password character set
import json # For handling JSONField in Radiologist form

from .models import (
    User, Patient, Doctor, Nurse, ProcurementOfficer, Department, Appointment,
    VitalSign, MedicalHistory, PhysicalExamination, Diagnosis, TreatmentPlan,
    LabTestRequest, LabTestResult, ImagingRequest, ImagingResult, Prescription,
    ConsentForm, Receptionist, LabTechnician, Radiologist, Pharmacist,
    Medication  # Assuming you have a Medication model for Prescription form
)

# --- Utility Functions ---

# Define prefixes for auto-generated usernames
USER_TYPE_PREFIXES = {
    'Patient': 'PT',
    'Doctor': 'DR',
    'Nurse': 'NS',
    'Pharmacist': 'PH',
    'ProcurementOfficer': 'PO',
    'Receptionist': 'RE',
    'LabTechnician': 'LT',
    'Radiologist': 'RD',
    'Administrator': 'ADM', # Example for admin, if applicable
}


def generate_unique_code(prefix):
    """
    Generates a unique username based on the prefix and the highest existing ID
    for users with that prefix.
    """
    # Find the last user whose username starts with the prefix and ends with digits.
    # This regex ensures we only consider usernames that follow the expected pattern.
    last_user = User.objects.filter(username__regex=rf'^{prefix}\d+$').order_by('-username').first()
    
    if last_user:
        try:
            # Extract the numeric part and increment it
            last_id = int(last_user.username[len(prefix):])
            new_id = last_id + 1
        except ValueError:
            # Fallback if for some reason the numeric part is not valid
            new_id = 1
    else:
        new_id = 1
    
    return f"{prefix}{new_id:03d}" # e.g., PT001, DR001


def generate_random_password(length=12):
    """
    Generates a strong random password with a mix of character types.
    """
    alphabet = string.ascii_letters
    digits = string.digits
    special_chars = string.punctuation

    # Ensure at least one character from each required set
    password_chars = [
        secrets.choice(alphabet),
        secrets.choice(digits),
        secrets.choice(special_chars)
    ]
    # Fill the remaining length with a random mix of all characters
    all_characters = alphabet + digits + special_chars
    password_chars += [secrets.choice(all_characters) for _ in range(length - len(password_chars))]
    
    # Shuffle the list to ensure randomness
    secrets.SystemRandom().shuffle(password_chars)
    return ''.join(password_chars)

# --- Base User Registration Form ---
class CustomUserCreationForm(UserCreationForm):
    """
    Base form for creating new User instances. It handles common user fields,
    auto-generates username and a temporary password, and hides password fields
    from the form display.
    """
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True, help_text="Required. Must be unique.")
    phone_number = forms.CharField(max_length=20, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
        required=False,
        help_text='Format: YYYY-MM-DD'
    )
    gender = forms.ChoiceField(choices=User.gender_choices, required=False) # Assuming User.gender_choices exists

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'first_name', 'last_name', 'email', 'phone_number',
            'address', 'date_of_birth', 'gender',
        )

    def __init__(self, *args, **kwargs):
        # --- IMPORTANT CHANGE HERE ---
        # Extract 'user_type' from kwargs before passing to the parent __init__
        self.user_type_from_view = kwargs.pop('user_type', None) 
        # Store it as an instance attribute if you need to access it later, 
        # e.g., in the clean() method, though for save() it's passed as an argument.
        # --- END IMPORTANT CHANGE ---

        super().__init__(*args, **kwargs) # Now, user_type is no longer in kwargs for the parent

        # Remove username and password fields as they are auto-generated
        if 'username' in self.fields:
            del self.fields['username']
        # Django's UserCreationForm creates 'password' and 'password2' by default.
        # We need to remove both.
        if 'password' in self.fields: 
            del self.fields['password']
        if 'password2' in self.fields: 
            del self.fields['password2']

        # Apply Bootstrap form-control class and placeholders
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput,
                                         forms.DateInput, forms.Textarea,
                                         forms.Select, forms.NumberInput)):
                field.widget.attrs['class'] = 'form-control'
            
            # Set specific placeholders
            if field_name == 'email':
                field.widget.attrs['placeholder'] = 'Enter email address'
            elif field_name == 'first_name':
                field.widget.attrs['placeholder'] = 'First Name'
            elif field_name == 'last_name':
                field.widget.attrs['placeholder'] = 'Last Name'
            elif field_name == 'phone_number':
                field.widget.attrs['placeholder'] = 'Phone Number'
            elif field_name == 'address':
                field.widget.attrs['placeholder'] = 'Full Address'
            # Add placeholders for other general fields as needed

    def clean_email(self):
        """Ensure email is unique across all users."""
        email = self.cleaned_data['email']
        if self.instance and self.instance.pk:
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("This email address is already registered.")
        elif User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email

    def save(self, commit=True, user_type=None):
        """
        Saves the user instance, auto-generating username and password,
        and setting the user_type.
        """
        user = super().save(commit=False) # Don't commit yet

        # Determine the prefix based on user_type passed to save method
        # Use the user_type passed as an argument first, then fallback to the one from __init__, then default
        prefix = USER_TYPE_PREFIXES.get(user_type or self.user_type_from_view, 'USR')
        user.username = generate_unique_code(prefix)

        raw_password = generate_random_password()
        user.set_password(raw_password) # Hash the password

        if user_type: # Ensure user_type is set on the user object
            user.user_type = user_type 

        # Handle is_staff/is_superuser flags based on user_type if your User model uses them
        if user_type == 'admin':
            user.is_staff = True
            user.is_superuser = True
        elif user_type in ['doctor', 'nurse', 'pharmacist', 'procurement_officer', 'receptionist', 'lab_tech', 'radiologist']:
            user.is_staff = True
            user.is_superuser = False # Ensure non-admin staff aren't superusers
        else: # For 'patient' or 'general'
            user.is_staff = False
            user.is_superuser = False

        if commit:
            user.save()
        
        # Store raw password temporarily on the user instance for access in the view (e.g., to email it)
        # This is a non-persistent attribute and will not be saved to the database.
        user._raw_password = raw_password 
        return user

## Specific User Type Registration Forms

class PatientRegistrationForm(CustomUserCreationForm):
    blood_group = forms.ChoiceField(choices=Patient.blood_group_choices, required=False)
    emergency_contact_name = forms.CharField(max_length=100, required=True)
    emergency_contact_phone = forms.CharField(max_length=20, required=True)
    allergies = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'List known allergies (e.g., medications, food)'}),
        required=False
    )
    pre_existing_conditions = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'List any chronic conditions'}),
        required=False
    )

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'blood_group', 'emergency_contact_name', 'emergency_contact_phone',
            'allergies', 'pre_existing_conditions',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap class and placeholders to new fields
        self.fields['blood_group'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_name'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_name'].widget.attrs['placeholder'] = 'Emergency Contact Name'
        self.fields['emergency_contact_phone'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_phone'].widget.attrs['placeholder'] = 'Emergency Contact Phone'
        self.fields['allergies'].widget.attrs['class'] = 'form-control'
        self.fields['pre_existing_conditions'].widget.attrs['class'] = 'form-control'


class DoctorRegistrationForm(CustomUserCreationForm):
    specialization = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Cardiology, Pediatrics'})
    )
    medical_license_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., KMPDB/DR/12345'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=True,
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'specialization', 'medical_license_number', 'department',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fields get 'form-control' from parent's __init__, just add placeholders
        self.fields['specialization'].widget.attrs['placeholder'] = 'e.g., Cardiology, Pediatrics'
        self.fields['medical_license_number'].widget.attrs['placeholder'] = 'e.g., KMPDB/DR/12345'


class NurseRegistrationForm(CustomUserCreationForm):
    # This field is expected to be on the Nurse profile model.
    nursing_license_number = forms.CharField(max_length=50, required=True)

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + ('nursing_license_number',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nursing_license_number'].widget.attrs['class'] = 'form-control'
        self.fields['nursing_license_number'].widget.attrs['placeholder'] = 'Enter Nursing License Number'


class PharmacistRegistrationForm(CustomUserCreationForm):
    # This field is expected to be on the Pharmacist profile model.
    pharmacy_license_number = forms.CharField(max_length=50, required=True)

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + ('pharmacy_license_number',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pharmacy_license_number'].widget.attrs['class'] = 'form-control'
        self.fields['pharmacy_license_number'].widget.attrs['placeholder'] = 'Enter Pharmacy License Number'


class ProcurementOfficerRegistrationForm(CustomUserCreationForm):
    # This field is expected to be on the ProcurementOfficer profile model.
    employee_id = forms.CharField(max_length=50, required=True, help_text="Procurement Officer Employee ID")
    
    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + ('employee_id',) # Add the field here for form input

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee_id'].widget.attrs['placeholder'] = 'Enter Employee ID'


class ReceptionistRegistrationForm(CustomUserCreationForm):
    # These fields are expected to be on the Receptionist profile model.
    shift_info = forms.CharField(max_length=100, required=False)
    assigned_desk = forms.CharField(max_length=50, required=False)

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + ('shift_info', 'assigned_desk',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shift_info'].widget.attrs['placeholder'] = 'Select Shift'
        self.fields['assigned_desk'].widget.attrs['placeholder'] = 'Assigned Desk Number/Area'


class LabTechnicianRegistrationForm(CustomUserCreationForm):
    # These fields are expected to be on the LabTechnician profile model.
    license_number = forms.CharField(max_length=100, required=True)
    specialization = forms.CharField(max_length=100, required=False)
    shift_info = forms.CharField(max_length=100, required=False)
    lab_section_assigned = forms.CharField(max_length=100, required=False)
    qualifications = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    status = forms.CharField(max_length=50, required=False) # Assuming a CharField for status

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'license_number', 'specialization', 'shift_info',
            'lab_section_assigned', 'qualifications', 'status',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['license_number'].widget.attrs['placeholder'] = 'Enter License Number'
        self.fields['specialization'].widget.attrs['placeholder'] = 'e.g., Clinical Pathology'
        self.fields['shift_info'].widget.attrs['placeholder'] = 'Lab Shift Information'
        self.fields['lab_section_assigned'].widget.attrs['placeholder'] = 'e.g., Hematology, Chemistry'


class RadiologistRegistrationForm(CustomUserCreationForm):
    # These fields are expected to be on the Radiologist profile model.
    medical_license_number = forms.CharField(max_length=50, required=True)
    sub_specialization = forms.CharField(max_length=100, required=False)
    date_hired = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
        required=False
    )
    on_call_status = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    # For JSONField, we use a Textarea and clean it in `clean_preferred_modalities`
    preferred_modalities = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': "e.g., ['MRI', 'CT'] or leave blank"}),
        required=False
    )
    qualifications = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    status = forms.CharField(max_length=50, required=False)

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'medical_license_number', 'sub_specialization', 'date_hired',
            'on_call_status', 'preferred_modalities', 'qualifications', 'status',
        )

    def clean_preferred_modalities(self):
        data = self.cleaned_data.get('preferred_modalities')
        if data:
            try:
                parsed_data = json.loads(data)
                if not isinstance(parsed_data, list):
                    raise forms.ValidationError("Please enter a valid JSON list (e.g., ['MRI', 'CT']).")
                return parsed_data
            except json.JSONDecodeError:
                # If it's not valid JSON, try to parse as comma-separated string
                return [item.strip() for item in data.split(',') if item.strip()]
        return [] # Return an empty list if no data or invalid data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medical_license_number'].widget.attrs['placeholder'] = 'Enter Medical License Number'
        self.fields['sub_specialization'].widget.attrs['placeholder'] = 'e.g., Musculoskeletal Imaging'
        self.fields['on_call_status'].widget.attrs['class'] = 'form-check-input' # Specific class for checkbox

## Custom User Change Form

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name', 'user_type',
            'phone_number', 'address', 'date_of_birth', 'gender',
            # Add other User model fields you want to be editable
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap class to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput,
                                         forms.DateInput, forms.Textarea,
                                         forms.Select, forms.NumberInput)):
                field.widget.attrs['class'] = 'form-control'
        # Remove password fields inherited from UserChangeForm if you manage password changes separately
        if 'password' in self.fields:
            del self.fields['password']


## Model Forms for Related Profiles and Clinical Data

class DoctorForm(forms.ModelForm):
    """Form for editing an existing Doctor profile."""
    class Meta:
        model = Doctor
        fields = ['specialization', 'medical_license_number', 'department']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class NurseForm(forms.ModelForm):
    """Form for editing an existing Nurse profile."""
    class Meta:
        model = Nurse
        fields = ['nursing_license_number'] # Add specific Nurse fields here

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['nursing_license_number'].widget.attrs['placeholder'] = 'Enter Nursing License Number'


class PharmacistForm(forms.ModelForm):
    """Form for editing an existing Pharmacist profile."""
    class Meta:
        model = Pharmacist
        fields = ['pharmacy_license_number'] # Add specific Pharmacist fields here

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['pharmacy_license_number'].widget.attrs['placeholder'] = 'Enter Pharmacy License Number'


class ProcurementOfficerForm(forms.ModelForm):
    """Form for editing an existing Procurement Officer profile."""
    class Meta:
        model = ProcurementOfficer
        fields = ['employee_id'] # Add specific Procurement Officer fields here

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['employee_id'].widget.attrs['placeholder'] = 'Enter Employee ID'


class ReceptionistForm(forms.ModelForm):
    """Form for editing an existing Receptionist profile."""
    class Meta:
        model = Receptionist
        fields = ['shift_info', 'assigned_desk']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['shift_info'].widget.attrs['placeholder'] = 'Select Shift'
        self.fields['assigned_desk'].widget.attrs['placeholder'] = 'Assigned Desk Number/Area'


class LabTechnicianForm(forms.ModelForm):
    """Form for editing an existing LabTechnician profile."""
    class Meta:
        model = LabTechnician
        fields = [
            'license_number', 'specialization', 'shift_info',
            'lab_section_assigned', 'qualifications', 'status'
        ]
        widgets = {
            'qualifications': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['license_number'].widget.attrs['placeholder'] = 'Enter License Number'
        self.fields['lab_section_assigned'].widget.attrs['placeholder'] = 'e.g., Hematology, Chemistry'


class RadiologistForm(forms.ModelForm):
    """Form for editing an existing Radiologist profile."""
    # This field needs special handling for JSONField
    preferred_modalities = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': "e.g., ['MRI', 'CT'] or leave blank"}),
        required=False
    )

    class Meta:
        model = Radiologist
        fields = [
            'medical_license_number', 'sub_specialization', 'date_hired',
            'on_call_status', 'preferred_modalities', 'qualifications', 'status'
        ]
        widgets = {
            'qualifications': forms.Textarea(attrs={'rows': 3}),
            'date_hired': forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
        }

    def clean_preferred_modalities(self):
        # This custom clean method will parse the input string into a JSON list
        data = self.cleaned_data.get('preferred_modalities')
        if data:
            try:
                parsed_data = json.loads(data)
                if not isinstance(parsed_data, list):
                    raise forms.ValidationError("Please enter a valid JSON list (e.g., ['MRI', 'CT']).")
                return parsed_data
            except json.JSONDecodeError:
                return [item.strip() for item in data.split(',') if item.strip()]
        return []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['medical_license_number'].widget.attrs['placeholder'] = 'Enter Medical License Number'
        self.fields['on_call_status'].widget.attrs['class'] = 'form-check-input'


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'reason_for_visit']
        widgets = {
            'appointment_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'reason_for_visit': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Main reason for visit'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].widget.attrs['class'] = 'form-control'
        self.fields['doctor'].widget.attrs['class'] = 'form-control'


class VitalSignForm(forms.ModelForm):
    class Meta:
        model = VitalSign
        fields = ['temperature', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate', 'respiratory_rate', 'oxygen_saturation', 'weight_kg', 'height_cm']
        widgets = {
            'temperature': forms.NumberInput(attrs={'placeholder': 'e.g., 37.0'}),
            'blood_pressure_systolic': forms.NumberInput(attrs={'placeholder': 'Systolic'}),
            'blood_pressure_diastolic': forms.NumberInput(attrs={'placeholder': 'Diastolic'}),
            'heart_rate': forms.NumberInput(attrs={'placeholder': 'BPM'}),
            'respiratory_rate': forms.NumberInput(attrs={'placeholder': 'Breaths/min'}),
            'oxygen_saturation': forms.NumberInput(attrs={'placeholder': 'e.g., 98.0'}),
            'weight_kg': forms.NumberInput(attrs={'placeholder': 'Weight (kg)'}),
            'height_cm': forms.NumberInput(attrs={'placeholder': 'Height (cm)'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class MedicalHistoryForm(forms.ModelForm):
    class Meta:
        model = MedicalHistory
        fields = ['chief_complaint', 'history_of_present_illness', 'past_medical_history', 'surgical_history', 'family_history', 'social_history', 'medication_history']
        widgets = {
            'chief_complaint': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Main reason for visit'}),
            'history_of_present_illness': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Detailed illness history'}),
            'past_medical_history': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Past medical conditions'}),
            'surgical_history': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Past surgeries'}),
            'family_history': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Family medical conditions'}),
            'social_history': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Lifestyle and social factors'}),
            'medication_history': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Current and past medications'}),
        }
    # __init__ method is handled by explicit widget definitions for class 'form-control'


class PhysicalExaminationForm(forms.ModelForm):
    class Meta:
        model = PhysicalExamination
        fields = ['general_appearance', 'head_and_neck', 'chest_and_lungs', 'heart_and_circulation', 'abdomen', 'musculoskeletal', 'neurological', 'skin', 'other_findings']
        widgets = {
            'general_appearance': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'General observation'}),
            'head_and_neck': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Head and Neck findings'}),
            'chest_and_lungs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Chest and Lungs findings'}),
            'heart_and_circulation': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Heart and Circulation findings'}),
            'abdomen': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Abdomen findings'}),
            'musculoskeletal': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Musculoskeletal findings'}),
            'neurological': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Neurological findings'}),
            'skin': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Skin findings'}),
            'other_findings': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any other relevant findings'}),
        }
    # __init__ method is handled by explicit widget definitions for class 'form-control'


class DiagnosisForm(forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ['icd10_code', 'diagnosis_text', 'is_primary']
        widgets = {
            'diagnosis_text': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Detailed diagnosis'}),
            'icd10_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ICD-10 Code (Optional)'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}) # Specific class for checkbox
        }
    # No need for __init__ as widgets handle styling


class TreatmentPlanForm(forms.ModelForm):
    class Meta:
        model = TreatmentPlan
        fields = ['treatment_description', 'recommendations', 'expected_return_date', 'status']
        widgets = {
            'treatment_description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Describe the treatment plan'}),
            'recommendations': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Further recommendations'}),
            'expected_return_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    # No need for __init__ as widgets handle styling


class LabTestRequestForm(forms.ModelForm):
    class Meta:
        model = LabTestRequest
        fields = ['tests', 'request_notes', 'status']
        widgets = {
            # Assuming 'tests' is a ManyToMany field to a 'Test' model or similar
            'tests': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'request_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Notes for lab technician'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure that if 'tests' is a ManyToMany, its queryset is set if needed in a view


class LabTestResultForm(forms.ModelForm):
    class Meta:
        model = LabTestResult
        fields = ['test', 'result_value', 'result_unit', 'normal_range_at_time_of_test', 'is_abnormal', 'comment', 'result_file']
        widgets = {
            'test': forms.Select(attrs={'class': 'form-control'}),
            'result_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Test result value'}),
            'result_unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unit (e.g., mg/dL)'}),
            'normal_range_at_time_of_test': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Normal range (e.g., 70-100)'}),
            'is_abnormal': forms.CheckboxInput(attrs={'class': 'form-check-input'}), # Specific class for checkbox
            'comment': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Additional comments'}),
            'result_file': forms.ClearableFileInput(attrs={'class': 'form-control'}), # For file uploads
        }
    # No need for __init__ as widgets handle styling


class ImagingRequestForm(forms.ModelForm):
    class Meta:
        model = ImagingRequest
        fields = ['imaging_type', 'reason_for_exam', 'body_part', 'status']
        widgets = {
            'imaging_type': forms.Select(attrs={'class': 'form-control'}),
            'reason_for_exam': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Reason for imaging exam'}),
            'body_part': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Body part to be imaged'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    # No need for __init__ as widgets handle styling


class ImagingResultForm(forms.ModelForm):
    class Meta:
        model = ImagingResult
        fields = ['radiologist', 'findings', 'impression', 'recommendations', 'image_files']
        widgets = {
            'radiologist': forms.Select(attrs={'class': 'form-control'}),
            'findings': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Findings from the imaging'}),
            'impression': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Radiologist impression'}),
            'recommendations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Recommendations (e.g., follow-up)'}),
            'image_files': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    # No need for __init__ as widgets handle styling


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medication', 'dosage', 'frequency', 'duration', 'route', 'notes']
        widgets = {
            'medication': forms.Select(attrs={'class': 'form-control'}), # Assuming 'medication' is a ForeignKey
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1 tablet'}),
            'frequency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Twice daily'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 7 days'}),
            'route': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Oral, IV'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Dispensing notes'}),
        }
    # No need for __init__ as widgets handle styling


class ConsentFormForm(forms.ModelForm):
    class Meta:
        model = ConsentForm
        fields = ['consent_type', 'consent_text', 'is_signed', 'signed_date', 'document_file']
        widgets = {
            'consent_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., General Treatment Consent'}),
            'consent_text': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'Full text of the consent form'}),
            'is_signed': forms.CheckboxInput(attrs={'class': 'form-check-input'}), # Specific class for checkbox
            'signed_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'document_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    # No need for __init__ as widgets handle styling