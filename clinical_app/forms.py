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
from datetime import date # For default value of report_date

from .models import (
    User, Patient, Doctor, Nurse, ProcurementOfficer, Department, Appointment,
    VitalSign, MedicalHistory, PhysicalExamination, Diagnosis, TreatmentPlan,
    LabTestRequest, LabTestResult, ImagingRequest, ImagingResult, Prescription,
    ConsentForm, Receptionist, LabTechnician, Radiologist, Pharmacist, ClinicalNote,
    Medication, Ward, Bed, BirthRecord, MortalityRecord, CancerRegistryReport 
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

class WardForm(forms.ModelForm):
    class Meta:
        model = Ward
        # EXCLUDE 'available_beds_count' and 'current_occupancy' from fields.
        # These are calculated properties and should not be directly editable via a form.
        fields = ['name', 'ward_type', 'capacity']
        # If you were using 'exclude', it would look like:
        # exclude = ['beds'] # Or other fields you don't want in the form.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to fields for styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput) or \
               isinstance(field.widget, forms.NumberInput) or \
               isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            # You can add more conditions for other widget types if needed

class BedCreateForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ['bed_number'] # Only bed_number needed for creation

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bed_number'].widget.attrs.update({'class': 'form-control'})


# Form for UPDATING an existing Bed (including patient assignment/unassignment)
class BedUpdateForm(forms.ModelForm):
    class Meta:
        model = Bed
        # We want to manage bed_number and patient here.
        # 'ward' is implicitly handled by the instance in an UpdateView.
        # 'is_occupied' is now a property, so it's not in the fields.
        fields = ['bed_number', 'patient']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Apply Bootstrap classes
        self.fields['bed_number'].widget.attrs.update({'class': 'form-control'})
        self.fields['patient'].widget.attrs.update({'class': 'form-select'})

        # Customize the queryset for the patient field
        # This ensures users can only select unassigned patients
        # OR the patient already assigned to THIS specific bed (if editing an existing assignment).
        
        # Patients who are currently not assigned to any bed
        unassigned_patients = Patient.objects.filter(current_bed__isnull=True)
        
        # If this form is for an existing Bed instance (self.instance is present)
        # AND that bed instance currently has a patient assigned to it
        if self.instance and self.instance.patient:
            # The queryset includes all unassigned patients PLUS the patient currently assigned to this bed.
            self.fields['patient'].queryset = unassigned_patients | Patient.objects.filter(pk=self.instance.patient.pk)
        else:
            # If creating a new bed (though this form is for update) or updating an empty bed,
            # only show unassigned patients.
            self.fields['patient'].queryset = unassigned_patients

        # Allow the patient field to be empty (for unassignment)
        self.fields['patient'].empty_label = "--- Select Patient (Leave blank to unassign) ---"
        self.fields['patient'].required = False

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


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        # List all fields you want to appear in the form.
        # Exclude 'created_at' and 'updated_at' as they are auto-populated.
        fields = [
            'name', 'description', 'department_type', 'head_of_department',
            'contact_phone', 'contact_email', 'location', 'floor_number',
            'staff_count', 'annual_budget', 'is_active',
        ]
        
        # Add widgets for Bootstrap styling
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department_type': forms.Select(attrs={'class': 'form-select'}),
            'head_of_department': forms.Select(attrs={'class': 'form-select'}), # This will show all users
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'floor_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'staff_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'annual_budget': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Optional: Customize queryset for head_of_department if only specific users can be HODs
    # For example, if only users with user_type='doctor' or 'admin' can be HODs
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users who can be assigned as Head of Department
        # This assumes your User model has a 'user_type' field and 'doctor' is a valid type.
        # Adjust 'doctor' or add other types like 'admin' as needed.
        # self.fields['head_of_department'].queryset = User.objects.filter(user_type='doctor') 
        # Or if you want all users to be selectable:
        self.fields['head_of_department'].queryset = User.objects.all().order_by('first_name', 'last_name') # Order for better UX
        # Add a blank choice at the top if the field can be null
        self.fields['head_of_department'].empty_label = "--- Select Head of Department ---"

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
class PatientForm(forms.ModelForm):
    # Fields from the User model that you want to allow updating
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")
    username = forms.CharField(max_length=150, required=True, label="Username")
    phone_number = forms.CharField(max_length=20, required=False, label="Phone Number")
    
    # Use the gender_choices from your Custom User model
    gender = forms.ChoiceField(choices=User.gender_choices, required=False, label="Gender")
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        label="Date of Birth"
    )

    class Meta:
        model = Patient
        fields = [
            # 'patient_id', # REMOVE patient_id from here as it's auto-generated and primary_key/not editable
            'blood_group',
            'emergency_contact_name',
            'emergency_contact_phone',
            'allergies',
            'pre_existing_conditions',
        ]
        widgets = {
            'allergies': forms.Textarea(attrs={'rows': 3, 'placeholder': 'List known allergies (e.g., medications, food)'}),
            'pre_existing_conditions': forms.Textarea(attrs={'rows': 3, 'placeholder': 'List any chronic conditions'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['username'].initial = self.instance.user.username
            self.fields['phone_number'].initial = self.instance.user.phone_number
            self.fields['gender'].initial = self.instance.user.gender
            self.fields['date_of_birth'].initial = self.instance.user.date_of_birth
        
        # Add Bootstrap form-control class to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.Textarea, forms.DateInput, forms.Select)):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})

        # Add a read-only field for patient_id if you want to display it
        # This is for display only, it won't be part of the form's data submission for update
        if self.instance and self.instance.patient_id:
            self.fields['display_patient_id'] = forms.CharField(
                label="Patient ID",
                initial=self.instance.patient_id,
                required=False,
                widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'})
            )
            # Reorder fields if you want display_patient_id to appear at the top
            self.order_fields(['display_patient_id', 'first_name', 'last_name', 'username', 'email', 'phone_number', 'gender', 'date_of_birth', 'blood_group', 'emergency_contact_name', 'emergency_contact_phone', 'allergies', 'pre_existing_conditions'])


    def clean_username(self):
        username = self.cleaned_data['username']
        # Check if username exists for another user (excluding the current user if updating)
        query = User.objects.filter(username=username)
        if self.instance and self.instance.user:
            query = query.exclude(pk=self.instance.user.pk)
        if query.exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        # Check if email exists for another user (excluding the current user if updating)
        query = User.objects.filter(email=email)
        if self.instance and self.instance.user:
            query = query.exclude(pk=self.instance.user.pk)
        if query.exists():
            raise forms.ValidationError("This email is already in use. Please use another.")
        return email

    def save(self, commit=True):
        # Retrieve the Patient instance created by super().save(commit=False)
        # Note: If primary_key=True, then super().save() might not create a new object
        # but modify the existing one based on the user's PK.
        patient = super().save(commit=False) # This will update Patient fields

        # Get the associated User instance
        user = patient.user

        # Update User fields from form data
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['username']
        user.phone_number = self.cleaned_data.get('phone_number')
        user.gender = self.cleaned_data.get('gender')
        user.date_of_birth = self.cleaned_data.get('date_of_birth')
        
        if commit:
            user.save() # Save the updated User instance
            patient.save() # Save the updated Patient instance (which also triggers patient_id generation if new)
        return patient


class DoctorForm(forms.ModelForm):
    """
    Form for editing an existing Doctor profile,
    including fields from the associated User model.
    """
    # Fields from the User model that you want to allow editing
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")
    phone_number = forms.CharField(max_length=20, required=False, label="Phone Number")
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Address")
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label="Date of Birth")
    gender = forms.ChoiceField(choices=User.gender_choices, required=False, label="Gender")

    class Meta:
        model = Doctor
        fields = [
            'specialization',
            'medical_license_number',
            'department',
            'years_of_experience', # Include 'years_of_experience' from Doctor model
            # User fields are defined explicitly above
        ]
        widgets = {
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'medical_license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}), # Add widget for this field
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate form fields with existing User data if an instance is provided
        if self.instance and self.instance.user:
            user_data = self.instance.user
            self.fields['first_name'].initial = user_data.first_name
            self.fields['last_name'].initial = user_data.last_name
            self.fields['email'].initial = user_data.email
            self.fields['phone_number'].initial = user_data.phone_number
            self.fields['address'].initial = user_data.address
            self.fields['date_of_birth'].initial = user_data.date_of_birth
            self.fields['gender'].initial = user_data.gender

        # Apply Bootstrap's 'form-control' class to all fields
        # This loop covers Meta fields and manually added fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.Select, forms.NumberInput, forms.DateInput)):
                field.widget.attrs.update({'class': 'form-control'})
            
            # Special handling for EmailField to ensure type='email'
            if field_name == 'email':
                field.widget.attrs['type'] = 'email'


    def save(self, commit=True):
        # First, save the Doctor instance but don't commit yet
        doctor = super().save(commit=False)

        # Then, update the associated User instance with cleaned data
        user = doctor.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data['phone_number']
        user.address = self.cleaned_data['address']
        user.date_of_birth = self.cleaned_data['date_of_birth']
        user.gender = self.cleaned_data['gender']

        # If commit is True, save both instances
        if commit:
            user.save()
            doctor.save() # This save might not be strictly necessary if primary_key=True is handled
                          # by Django's OneToOneField, but it's safer.
        return doctor

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


# In clinical_app/forms.py
class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'reason_for_visit']
        # Add 'status' only when editing if needed
        # widgets... (remain same)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Apply initial Bootstrap classes
        self.fields['patient'].widget.attrs['class'] = 'form-control'
        self.fields['doctor'].widget.attrs['class'] = 'form-control'
        
        # Set empty labels for Select2
        self.fields['patient'].empty_label = "Search and select a Patient"
        self.fields['doctor'].empty_label = "Search and select a Doctor"


        # Conditional display/initialization based on user type
        if self.user:
            if self.user.user_type == 'patient':
                # Hide the patient field, it will be set automatically
                self.fields['patient'].widget = forms.HiddenInput()
                # Initial value will be set in the view's form_valid
                self.fields['doctor'].queryset = Doctor.objects.all().order_by('user__first_name') # Patients can choose any doctor
            
            elif self.user.user_type == 'doctor':
                # Hide the doctor field, it will be set automatically
                self.fields['doctor'].widget = forms.HiddenInput()
                # Doctors can choose any patient
                self.fields['patient'].queryset = Patient.objects.all().order_by('user__first_name')
            
            elif self.user.user_type in ['admin', 'receptionist']:
                # Admin/Receptionist sees searchable fields for both
                self.fields['patient'].queryset = Patient.objects.all().order_by('user__first_name')
                self.fields['doctor'].queryset = Doctor.objects.all().order_by('user__first_name')
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


# class LabTestResultForm(forms.ModelForm):
#     class Meta:
#         model = LabTestResult
#         # 'request', 'performed_by', and 'result_date' are set in the view
#         fields = ['result_value', 'request_notes', 'is_normal']
#         labels = {
#             'result_value': 'Result Value/Observation',
#             'request_notes': 'Lab Technician Notes',
#             'is_normal': 'Is Result Normal?'
#         }
#         widgets = {
#             'result_value': forms.TextInput(attrs={'placeholder': 'e.g., 5.2 mg/dL or "Positive" or "No growth observed"'}),
#             'request_notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter any additional notes, interpretation, or details about the test result.'}),
#             'is_normal': forms.CheckboxInput(),
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         for field_name, field in self.fields.items():
#             if field_name != 'is_normal': # Checkboxes are styled differently
#                 if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.Select)):
#                     field.widget.attrs['class'] = 'form-control'
#             else: # For checkbox
#                 field.widget.attrs['class'] = 'form-check-input'

class LabTestRequestForm(forms.ModelForm):
    """
    Form for creating or updating a LabTestRequest.
    """
    class Meta:
        model = LabTestRequest
        # Fields that the user will input directly:
        # - 'encounter' will typically be set by the view (e.g., from URL kwargs or session)
        # - 'requested_by' will be set automatically to request.user in the view
        # - 'requested_date' is auto_now_add
        # - 'status' defaults to 'pending' for new requests
        fields = ['tests', 'request_notes']
        labels = {
            'tests': 'Select Lab Tests to Order',
            'request_notes': 'Additional Request Notes for Lab',
        }
        widgets = {
            # Use CheckboxSelectMultiple for a user-friendly selection of multiple tests
            'tests': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input-group'}),
            'request_notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Provide any specific instructions or clinical notes for the lab technician here.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes for styling
        for field_name, field in self.fields.items():
            if field_name == 'tests':
                # For CheckboxSelectMultiple, the class usually applies to individual checkboxes
                # We can style the container or individual items in the template if needed.
                # field.widget.attrs['class'] is not directly applicable to the wrapper div.
                pass
            else:
                # Apply 'form-control' to other input types
                if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.Select)):
                    field.widget.attrs['class'] = 'form-control'

        # Optionally, if you want to ensure the 'tests' queryset is ordered
        self.fields['tests'].queryset = LabTest.objects.all().order_by('name')


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

class ClinicalNoteForm(forms.ModelForm):
    class Meta:
        model = ClinicalNote
        fields = [
            'chief_complaint',
            'history_of_present_illness',
            'review_of_systems',
            'physical_exam_findings',
            'assessment',
            'plan',
            'primary_diagnosis',
            'secondary_diagnoses',
            'interventions_performed',
            'medications_prescribed',
            'follow_up_instructions',
        ]
        widgets = {
            'chief_complaint': forms.Textarea(attrs={'rows': 3}),
            'history_of_present_illness': forms.Textarea(attrs={'rows': 4}),
            'review_of_systems': forms.Textarea(attrs={'rows': 4}),
            'physical_exam_findings': forms.Textarea(attrs={'rows': 5}),
            'assessment': forms.Textarea(attrs={'rows': 5}),
            'plan': forms.Textarea(attrs={'rows': 6}),
            'secondary_diagnoses': forms.Textarea(attrs={'rows': 2}),
            'interventions_performed': forms.Textarea(attrs={'rows': 4}),
            'medications_prescribed': forms.Textarea(attrs={'rows': 4}),
            'follow_up_instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all fields manually
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control' # This makes fields look like Bootstrap inputs
            # Ensure textarea rows are set, in case widgets dict above is sometimes missed
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = field.widget.attrs.get('rows', 4) 
            # You can also add more classes or attributes here based on field type
            # Example: if field_name == 'chief_complaint': field.widget.attrs['placeholder'] = 'Patient\'s main reason for visit'
            if field.required:
                field.label = f"{field.label} *" # Add asterisk for required fields

class BirthRecordForm(forms.ModelForm):
    class Meta:
        model = BirthRecord
        fields = '__all__' # Or specify individual fields: ['patient', 'baby_name', ...]
        # Add widgets for better UX, e.g., date pickers
        widgets = {
            'date_of_birth': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class MortalityRecordForm(forms.ModelForm):
    class Meta:
        model = MortalityRecord
        fields = '__all__' # This is fine as it includes all your model fields
        widgets = {
            'date_of_death': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'), # Added format
            'cause_of_death': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'contributing_factors': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'death_location': forms.Select(attrs={'class': 'form-select'}),
            # patient, full_name, encounter, certified_by, certificate_number handled automatically
        }
    
    # Custom cleaning for patient/full_name exclusivity
    def clean(self):
        cleaned_data = super().clean()
        patient = cleaned_data.get('patient')
        full_name = cleaned_data.get('full_name')

        if not patient and not full_name:
            raise forms.ValidationError(
                "Either a patient record must be linked OR a full name must be provided."
            )
        if patient and full_name:
            # You might allow both but prioritize `patient`, or disallow both.
            # For simplicity, let's say you should only provide one for a new record.
            # Or you can just let 'patient' override 'full_name' in your logic.
            # Here, we'll allow both but indicate a potential redundancy.
            pass # Or raise a specific error if you want strict exclusivity:
            # raise forms.ValidationError(
            #    "Please link either a patient record or provide a full name, but not both."
            # )
        return cleaned_data

class MedicationForm(forms.ModelForm):
    class Meta:
        model = Medication
        fields = '__all__' # Includes name, strength, form, manufacturer, price_per_unit, stock_quantity, reorder_level
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'strength': forms.TextInput(attrs={'class': 'form-control'}),
            'form': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

# New Cancer Registry Report Form
class CancerRegistryReportForm(forms.ModelForm):
    class Meta:
        model = CancerRegistryReport
        fields = '__all__' # Include all fields from the model
        widgets = {
            'report_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_of_diagnosis': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_of_last_follow_up': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_of_death': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'cancer_type': forms.TextInput(attrs={'class': 'form-control'}),
            'stage': forms.TextInput(attrs={'class': 'form-control'}),
            'treatment_modalities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'cause_of_death': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'vital_status': forms.Select(attrs={'class': 'form-select'}),
            'reported_to_registry': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'registry_submission_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'patient': forms.Select(attrs={'class': 'form-select'}), # Style for select fields
            'diagnosis': forms.Select(attrs={'class': 'form-select'}), # Style for select fields
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default for report_date if creating a new report
        if not self.instance.pk: # Only for new instances
            self.fields['report_date'].initial = date.today()
            # If reported_to_registry is true, registry_submission_date should be required
            self.fields['registry_submission_date'].required = False # Default to not required

    def clean(self):
        cleaned_data = super().clean()
        reported_to_registry = cleaned_data.get('reported_to_registry')
        registry_submission_date = cleaned_data.get('registry_submission_date')
        vital_status = cleaned_data.get('vital_status')
        date_of_death = cleaned_data.get('date_of_death')
        cause_of_death = cleaned_data.get('cause_of_death')

        # If reported_to_registry is true, registry_submission_date must be provided
        if reported_to_registry and not registry_submission_date:
            self.add_error('registry_submission_date', "Submission date is required if reported to registry.")
        
        # If vital_status is 'dead', date_of_death should be required
        if vital_status == 'dead' and not date_of_death:
            self.add_error('date_of_death', "Date of death is required if vital status is 'Dead'.")
        # If vital_status is 'dead' and date_of_death is provided, cause_of_death might be required
        if vital_status == 'dead' and date_of_death and not cause_of_death:
             self.add_error('cause_of_death', "Cause of death is recommended if vital status is 'Dead'.")
        
        # If vital_status is 'alive', date_of_death and cause_of_death should be empty
        if vital_status == 'alive' and (date_of_death or cause_of_death):
            self.add_error('vital_status', "Date of death and cause of death must be empty if vital status is 'Alive'.")
            # Optionally clear the fields
            cleaned_data['date_of_death'] = None
            cleaned_data['cause_of_death'] = ''

        return cleaned_data

class ImagingResultForm(forms.ModelForm):
    class Meta:
        model = ImagingResult
        # Fields must match your model's fields exactly
        fields = ['report_date', 'findings', 'impression', 'recommendations', 'image_files', 'radiologist']
        widgets = {
            # Map 'result_date' to 'report_date'
            'report_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'findings': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            # Map 'conclusion' to 'impression'
            'impression': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'recommendations': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'image_files': forms.ClearableFileInput(attrs={'class': 'form-control'}), # Keep this without 'multiple'
            'radiologist': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value for report_date to now
        if not self.instance.pk:
            self.fields['report_date'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
