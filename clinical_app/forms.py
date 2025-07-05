from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, Patient, Doctor, Nurse, ProcurementOfficer, Department, Appointment, VitalSign, MedicalHistory, PhysicalExamination, Diagnosis, TreatmentPlan, LabTestRequest, LabTestResult, ImagingRequest, ImagingResult, Prescription, ConsentForm, Receptionist, LabTechnician, Radiologist

# --- Base User Registration Form ---
# This form will handle the common fields for all user types.
# It inherits from Django's UserCreationForm for username/password handling.

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
        required=False,
        help_text='Format: YYYY-MM-DD'
    )
    gender = forms.ChoiceField(choices=User.gender_choices, required=False) # Use User.gender_choices

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + (
            'first_name', 'last_name', 'email', 'phone_number',
            'address', 'date_of_birth', 'gender',
        )
        labels = {
            'username': 'Username',
            'password': 'Password',
            'password2': 'Confirm Password',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.PasswordInput, forms.EmailInput,
                                         forms.DateInput, forms.Textarea, forms.Select)):
                field.widget.attrs['class'] = 'form-control'
            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Enter username'
            elif field_name == 'email':
                field.widget.attrs['placeholder'] = 'Enter email address'
            elif field_name == 'first_name':
                field.widget.attrs['placeholder'] = 'First Name'
            elif field_name == 'last_name':
                field.widget.attrs['placeholder'] = 'Last Name'
            elif field_name == 'phone_number':
                field.widget.attrs['placeholder'] = 'Phone Number'
            elif field_name == 'address':
                field.widget.attrs['placeholder'] = 'Full Address'
            elif field_name == 'password':
                field.widget.attrs['placeholder'] = 'Password'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Confirm Password'


# --- Specific User Type Registration Forms ---
# These forms inherit from CustomUserCreationForm and add role-specific fields.

class PatientRegistrationForm(CustomUserCreationForm):
    # Patient-specific fields directly from the Patient model
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
        # We still specify User model here because this form's purpose is to create a User.
        # The related Patient object will be created in the view.
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'blood_group', 'emergency_contact_name', 'emergency_contact_phone',
            'allergies', 'pre_existing_conditions',
            # 'user_type' is handled in __init__ and view, not directly exposed here
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap class and placeholders to new fields
        self.fields['blood_group'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_name'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_name'].widget.attrs['placeholder'] = 'Emergency Contact Name'
        self.fields['emergency_contact_phone'].widget.attrs['class'] = 'form-control'
        self.fields['emergency_contact_phone'].widget.attrs['placeholder'] = 'Emergency Contact Phone'
        self.fields['allergies'].widget.attrs['class'] = 'form-control'
        self.fields['pre_existing_conditions'].widget.attrs['class'] = 'form-control'


class DoctorRegistrationForm(CustomUserCreationForm):
    # Doctor-specific fields
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
        required=True, # Make department required for doctors
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-control'}) # Apply class here
    )

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'specialization', 'medical_license_number', 'department',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All fields get 'form-control' from parent init, just ensure placeholders for specific fields
        self.fields['specialization'].widget.attrs['class'] = 'form-control'
        self.fields['medical_license_number'].widget.attrs['class'] = 'form-control'


class NurseRegistrationForm(CustomUserCreationForm):
    # Add any nurse-specific fields here if they exist, e.g.:
    # years_of_experience = forms.IntegerField(required=False, min_value=0,
    #                                         widget=forms.NumberInput(attrs={'placeholder': 'Years of Experience'}))

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            # 'years_of_experience', # Add if you uncomment the field above
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If you add nurse-specific fields, ensure their styling here
        # if 'years_of_experience' in self.fields:
        #     self.fields['years_of_experience'].widget.attrs['class'] = 'form-control'


# For other staff types (Pharmacist, Lab Technician, Radiologist, Receptionist, Admin)
# If they don't have additional profile models or unique fields beyond the base User model,
# you can use `CustomUserCreationForm` directly in your view. If they do, create a new form:

class PharmacistRegistrationForm(CustomUserCreationForm):
    # Add pharmacist-specific fields if any
    # Example: pharmacy_license_number = forms.CharField(max_length=50, required=True)
    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            # 'pharmacy_license_number',
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if 'pharmacy_license_number' in self.fields:
        #     self.fields['pharmacy_license_number'].widget.attrs['class'] = 'form-control'

class ProcurementOfficerRegistrationForm(CustomUserCreationForm):
    employee_id = forms.CharField(max_length=50, required=True, help_text="Procurement Officer Employee ID")
    # Add other fields specific to ProcurementOfficer if any

    class Meta(CustomUserCreationForm.Meta):
        model = User
        fields = CustomUserCreationForm.Meta.fields + (
            'employee_id', # This field is on the ProcurementOfficer model, not User.
                           # We handle it in the save method.
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove user_type if you don't want it explicitly shown or changed in this form
        if 'user_type' in self.fields:
            del self.fields['user_type']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'procurement_officer' # Explicitly set user type for this form
        if commit:
            user.save()
            procurement_officer_profile = ProcurementOfficer.objects.create(
                user=user,
                employee_id=self.cleaned_data['employee_id'],
            )
        return user

# --- Custom User Change Form (for editing existing users) ---
class CustomUserChangeForm(UserChangeForm):
    # You might want to remove password fields for change form if not needed for editing
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'phone_number', 'address', 'date_of_birth', 'gender',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput,
                                         forms.DateInput, forms.Textarea, forms.Select)):
                field.widget.attrs['class'] = 'form-control'

# --- Existing ModelForms (no changes to these, just for context) ---

class DoctorForm(forms.ModelForm): # This is likely for *editing* an existing Doctor profile
    class Meta:
        model = Doctor
        fields = ['specialization', 'medical_license_number', 'department']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class ReceptionistRegistrationForm(forms.ModelForm):
    class Meta:
        model = Receptionist
        fields = ['shift_info', 'assigned_desk']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['shift_info'].widget.attrs['placeholder'] = 'Select Shift'
        self.fields['assigned_desk'].widget.attrs['placeholder'] = 'Assigned Desk Number/Area'


class LabTechnicianRegistrationForm(forms.ModelForm):
    """
    Form for LabTechnician-specific profile fields.
    """
    class Meta:
        model = LabTechnician
        # Only include fields that are directly on the LabTechnician model
        fields = [
            'license_number', 'specialization', 'shift_info',
            'lab_section_assigned', 'qualifications', 'status'
        ]
        # You can add widgets or help texts here if needed
        widgets = {
            'qualifications': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['license_number'].widget.attrs['placeholder'] = 'Enter License Number'
        self.fields['lab_section_assigned'].widget.attrs['placeholder'] = 'e.g., Hematology, Chemistry'


class RadiologistRegistrationForm(forms.ModelForm):
    """
    Form for Radiologist-specific profile fields.
    """
    class Meta:
        model = Radiologist
        # Only include fields that are directly on the Radiologist model
        fields = [
            'medical_license_number', 'sub_specialization', 'date_hired',
            'on_call_status', 'preferred_modalities', 'qualifications', 'status'
        ]
        widgets = {
            'qualifications': forms.Textarea(attrs={'rows': 3}),
            'date_hired': forms.DateInput(attrs={'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            # For JSONField, you might need a custom widget or convert to CharField
            # for simpler form handling if not using advanced form libraries.
            # A simple way to handle preferred_modalities as JSON in the form:
            'preferred_modalities': forms.Textarea(attrs={'rows': 2, 'placeholder': "e.g., ['MRI', 'CT'] or leave blank"}),
        }


    def clean_preferred_modalities(self):
        # This custom clean method will parse the input string into a JSON list
        data = self.cleaned_data.get('preferred_modalities')
        if data:
            import json
            try:
                # Attempt to parse as JSON. If it's a simple string, convert to list.
                parsed_data = json.loads(data)
                if not isinstance(parsed_data, list):
                    raise forms.ValidationError("Please enter a valid JSON list (e.g., ['MRI', 'CT']).")
                return parsed_data
            except json.JSONDecodeError:
                # If it's not JSON, treat it as a comma-separated string
                return [item.strip() for item in data.split(',') if item.strip()]
        return [] # Return an empty list if no data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['medical_license_number'].widget.attrs['placeholder'] = 'Enter Medical License Number'
        self.fields['on_call_status'].widget.attrs['class'] = 'form-check-input' # For checkbox styling

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'reason_for_visit']
        widgets = {
            'appointment_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'reason_for_visit': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All widgets explicitly set class 'form-control' above, no need to loop here unless adding more dynamic attributes

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All widgets explicitly set class 'form-control' above

class DiagnosisForm(forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ['icd10_code', 'diagnosis_text', 'is_primary']
        widgets = {
            'diagnosis_text': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Detailed diagnosis'}),
            'icd10_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ICD-10 Code (Optional)'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'is_primary' checkbox needs no special class
        if 'is_primary' in self.fields:
            self.fields['is_primary'].widget.attrs.pop('class', None) # Remove form-control from checkbox if it got applied

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Widgets explicitly set class 'form-control' above

class LabTestRequestForm(forms.ModelForm):
    class Meta:
        model = LabTestRequest
        fields = ['tests', 'request_notes', 'status']
        widgets = {
            'tests': forms.SelectMultiple(attrs={'class': 'form-control'}), # Use SelectMultiple for ManyToMany
            'request_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Notes for lab technician'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class LabTestResultForm(forms.ModelForm):
    class Meta:
        model = LabTestResult
        fields = ['test', 'result_value', 'result_unit', 'normal_range_at_time_of_test', 'is_abnormal', 'comment', 'result_file']
        widgets = {
            'test': forms.Select(attrs={'class': 'form-control'}),
            'result_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Test result value'}),
            'result_unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unit (e.g., mg/dL)'}),
            'normal_range_at_time_of_test': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Normal range (e.g., 70-100)'}),
            'comment': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Additional comments'}),
            'result_file': forms.ClearableFileInput(attrs={'class': 'form-control'}), # For file uploads
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'is_abnormal' in self.fields:
            self.fields['is_abnormal'].widget.attrs.pop('class', None) # Remove form-control from checkbox

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medication', 'dosage', 'frequency', 'duration', 'route', 'notes']
        widgets = {
            'medication': forms.Select(attrs={'class': 'form-control'}),
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1 tablet'}),
            'frequency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Twice daily'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 7 days'}),
            'route': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Oral, IV'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Dispensing notes'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class ConsentFormForm(forms.ModelForm):
    class Meta:
        model = ConsentForm
        fields = ['consent_type', 'consent_text', 'is_signed', 'signed_date', 'document_file']
        widgets = {
            'consent_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., General Treatment Consent'}),
            'consent_text': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'Full text of the consent form'}),
            'signed_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'document_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'is_signed' in self.fields:
            self.fields['is_signed'].widget.attrs.pop('class', None) # Remove form-control from checkbox