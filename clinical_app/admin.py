from django.contrib import admin
from .models import (
    User, Doctor, Nurse, Department, Patient, ProcurementOfficer, ConsentForm,
    Appointment, Encounter, VitalSign, MedicalHistory, PhysicalExamination,
    Diagnosis, TreatmentPlan, LabTestCategory, LabTest, LabTestRequest,
    LabTestResult, ImagingType, ImagingRequest, ImagingResult, Medication,
    Prescription, Ward, Bed, CaseSummary, CancerRegistryReport,
    BirthRecord, MortalityRecord, ActivityLog
)

# Register your models here.

# Customizing User Admin (optional but recommended for a custom User model)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    list_filter = ('user_type', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address', 'date_of_birth', 'gender', 'user_type')}),
        (('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    ordering = ('-date_joined',)

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user_full_name', 'specialization', 'medical_license_number', 'department')
    search_fields = ('user__first_name', 'user__last_name', 'specialization', 'medical_license_number')
    list_filter = ('specialization', 'department')
    raw_id_fields = ('user', 'department') # Use raw_id_fields for ForeignKey/OneToOne to avoid dropdowns with many items

    def user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    user_full_name.short_description = 'Doctor Name'

@admin.register(Nurse)
class NurseAdmin(admin.ModelAdmin):
    list_display = ('user_full_name',)
    search_fields = ('user__first_name', 'user__last_name')
    raw_id_fields = ('user',)

    def user_full_name(self, obj):
        return f"Nurse {obj.user.first_name} {obj.user.last_name}"
    user_full_name.short_description = 'Nurse Name'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'user_full_name', 'blood_group', 'emergency_contact_name', 'registration_date')
    search_fields = ('patient_id', 'user__first_name', 'user__last_name', 'emergency_contact_name')
    list_filter = ('blood_group', 'registration_date')
    readonly_fields = ('patient_id', 'registration_date')
    raw_id_fields = ('user',)

    def user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    user_full_name.short_description = 'Patient Name'

@admin.register(ProcurementOfficer)
class ProcurementOfficerAdmin(admin.ModelAdmin):
    list_display = ('user_full_name', 'employee_id')
    search_fields = ('user__first_name', 'user__last_name', 'employee_id')
    # You could add list_filter here if ProcurementOfficer had more fields, e.g., 'department'
    raw_id_fields = ('user',) # Useful for selecting the associated User

    def user_full_name(self, obj):
        return f"Procurement Officer {obj.user.first_name} {obj.user.last_name}"
    user_full_name.short_description = 'Procurement Officer Name'

@admin.register(ConsentForm)
class ConsentFormAdmin(admin.ModelAdmin):
    list_display = ('patient', 'consent_type', 'is_signed', 'signed_date', 'signed_by_staff')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'consent_type')
    list_filter = ('consent_type', 'is_signed')
    raw_id_fields = ('patient', 'signed_by_staff')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'status')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'doctor__user__first_name', 'doctor__user__last_name')
    list_filter = ('status', 'appointment_date')
    raw_id_fields = ('patient', 'doctor')
    date_hierarchy = 'appointment_date'

@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'encounter_date', 'encounter_type', 'ward', 'bed')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'doctor__user__first_name', 'doctor__user__last_name')
    list_filter = ('encounter_type', 'encounter_date', 'ward')
    raw_id_fields = ('patient', 'doctor', 'appointment', 'ward', 'bed')
    date_hierarchy = 'encounter_date'

@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'temperature', 'blood_pressure_systolic', 'heart_rate', 'timestamp', 'recorded_by')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'recorded_by__username')
    list_filter = ('timestamp', 'recorded_by')
    raw_id_fields = ('encounter', 'recorded_by')

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(MedicalHistory)
class MedicalHistoryAdmin(admin.ModelAdmin):
    list_display = ('patient', 'recorded_by', 'recorded_date', 'chief_complaint')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'chief_complaint')
    list_filter = ('recorded_date', 'recorded_by')
    raw_id_fields = ('patient', 'recorded_by')
    date_hierarchy = 'recorded_date'

@admin.register(PhysicalExamination)
class PhysicalExaminationAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'examined_by', 'examination_date')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name')
    list_filter = ('examination_date', 'examined_by')
    raw_id_fields = ('encounter', 'examined_by')
    date_hierarchy = 'examination_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'diagnosis_text', 'icd10_code', 'is_primary', 'diagnosis_date', 'diagnosed_by')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'diagnosis_text', 'icd10_code')
    list_filter = ('is_primary', 'diagnosis_date', 'diagnosed_by')
    raw_id_fields = ('encounter', 'diagnosed_by')
    date_hierarchy = 'diagnosis_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'created_by', 'created_date', 'status', 'expected_return_date')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'treatment_description')
    list_filter = ('status', 'created_date', 'created_by')
    raw_id_fields = ('encounter', 'created_by')
    date_hierarchy = 'created_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(LabTestCategory)
class LabTestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'unit', 'normal_range', 'price')
    search_fields = ('name', 'category__name')
    list_filter = ('category',)

@admin.register(LabTestRequest)
class LabTestRequestAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'requested_by', 'requested_date', 'status')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'tests__name')
    list_filter = ('status', 'requested_date')
    raw_id_fields = ('encounter', 'requested_by', 'tests') # tests is ManyToMany
    date_hierarchy = 'requested_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(LabTestResult)
class LabTestResultAdmin(admin.ModelAdmin):
    list_display = ('request_patient', 'test', 'result_value', 'is_abnormal', 'result_date', 'performed_by')
    search_fields = ('request__encounter__patient__user__first_name', 'request__encounter__patient__user__last_name', 'test__name', 'result_value')
    list_filter = ('is_abnormal', 'result_date', 'performed_by')
    raw_id_fields = ('request', 'test', 'performed_by')
    date_hierarchy = 'result_date'

    def request_patient(self, obj):
        return obj.request.encounter.patient.__str__()
    request_patient.short_description = 'Patient'

@admin.register(ImagingType)
class ImagingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')
    search_fields = ('name',)

@admin.register(ImagingRequest)
class ImagingRequestAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'imaging_type', 'requested_by', 'requested_date', 'status')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'imaging_type__name')
    list_filter = ('status', 'requested_date', 'imaging_type')
    raw_id_fields = ('encounter', 'requested_by', 'imaging_type')
    date_hierarchy = 'requested_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(ImagingResult)
class ImagingResultAdmin(admin.ModelAdmin):
    list_display = ('request_patient', 'imaging_type', 'radiologist', 'report_date')
    search_fields = ('request__encounter__patient__user__first_name', 'request__encounter__patient__user__last_name', 'request__imaging_type__name', 'findings', 'impression')
    list_filter = ('report_date', 'radiologist')
    raw_id_fields = ('request', 'radiologist')
    date_hierarchy = 'report_date'

    def request_patient(self, obj):
        return obj.request.encounter.patient.__str__()
    request_patient.short_description = 'Patient'

    def imaging_type(self, obj):
        return obj.request.imaging_type.name
    imaging_type.short_description = 'Imaging Type'

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'strength', 'form', 'manufacturer', 'price_per_unit')
    search_fields = ('name', 'strength', 'manufacturer')
    list_filter = ('form',)

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'medication', 'dosage', 'frequency', 'prescribed_by', 'prescription_date', 'is_dispensed')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'medication__name', 'dosage')
    list_filter = ('is_dispensed', 'prescription_date', 'prescribed_by')
    raw_id_fields = ('encounter', 'prescribed_by', 'medication', 'dispensed_by')
    date_hierarchy = 'prescription_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('name', 'ward_type', 'capacity')
    search_fields = ('name',)
    list_filter = ('ward_type',)

@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('ward', 'bed_number', 'is_occupied')
    search_fields = ('ward__name', 'bed_number')
    list_filter = ('is_occupied', 'ward')

@admin.register(CaseSummary)
class CaseSummaryAdmin(admin.ModelAdmin):
    list_display = ('encounter_patient', 'prepared_by', 'summary_date')
    search_fields = ('encounter__patient__user__first_name', 'encounter__patient__user__last_name', 'summary_text')
    list_filter = ('summary_date', 'prepared_by')
    raw_id_fields = ('encounter', 'prepared_by')
    date_hierarchy = 'summary_date'

    def encounter_patient(self, obj):
        return obj.encounter.patient.__str__()
    encounter_patient.short_description = 'Patient'

@admin.register(CancerRegistryReport)
class CancerRegistryReportAdmin(admin.ModelAdmin):
    list_display = ('patient', 'cancer_type', 'stage', 'report_date', 'vital_status', 'reported_to_registry')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'cancer_type', 'icd10_code')
    list_filter = ('cancer_type', 'stage', 'vital_status', 'reported_to_registry', 'report_date')
    raw_id_fields = ('patient', 'diagnosis')
    date_hierarchy = 'report_date'

@admin.register(BirthRecord)
class BirthRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'baby_name', 'date_of_birth', 'gender', 'weight_kg', 'delivered_by')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'baby_name')
    list_filter = ('date_of_birth', 'gender', 'delivered_by', 'is_multiple_birth')
    raw_id_fields = ('patient', 'delivered_by')
    date_hierarchy = 'date_of_birth'

@admin.register(MortalityRecord)
class MortalityRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date_of_death', 'cause_of_death', 'certified_by')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'cause_of_death')
    list_filter = ('date_of_death', 'certified_by')
    raw_id_fields = ('patient', 'certified_by')
    date_hierarchy = 'date_of_death'

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'model_name', 'object_id', 'ip_address')
    list_filter = ('action_type', 'model_name', 'timestamp')
    search_fields = ('user__username', 'user__email', 'model_name', 'object_id', 'description')
    readonly_fields = ('timestamp', 'user', 'action_type', 'ip_address', 'model_name', 'object_id', 'description', 'changes')
    ordering = ('-timestamp',)

    fieldsets = (
        (None, {
            'fields': (
                'timestamp', 'user', 'ip_address', 'action_type',
                'model_name', 'object_id', 'description', 'changes'
            )
        }),
    )

    def has_add_permission(self, request):
        return False  # Prevent manual addition of logs

    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing of existing logs
