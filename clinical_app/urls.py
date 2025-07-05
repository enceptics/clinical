from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
# 
urlpatterns = [
    # Auth URLs
    path('login/', auth_views.LoginView.as_view(template_name='clinical_app/user_management/user_login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('register/', views.select_user_type, name='select_user_type'),
    path('register/<str:user_type>/', views.UserRegistrationView.as_view(), name='register_by_type'),

    path('', views.HomeView.as_view(), name='home'),

    # Patient URLs
    path('patients/', views.PatientListView.as_view(), name='patient_list'),
    path('patients/create/', views.PatientCreateView.as_view(), name='patient_create'),
    path('patients/<int:pk>/', views.PatientDetailView.as_view(), name='patient_detail'),
    path('patients/<int:pk>/update/', views.PatientUpdateView.as_view(), name='patient_update'),
    path('patients/<int:patient_pk>/add_consent/', views.ConsentFormCreateView.as_view(), name='consent_create'),
    path('patients/<int:patient_pk>/add_history/', views.MedicalHistoryCreateView.as_view(), name='medical_history_create'),

    # Encounter URLs
    path('encounters/create/', views.EncounterCreateView.as_view(), name='encounter_create'),
    path('encounters/<int:pk>/', views.EncounterDetailView.as_view(), name='encounter_detail'),

    # Encounter Sub-Form URLs (related to a specific encounter)
    path('encounters/<int:encounter_pk>/vitals/add/', views.VitalSignCreateView.as_view(), name='vitals_create'),
    path('encounters/<int:encounter_pk>/physical_exam/add/', views.PhysicalExaminationCreateView.as_view(), name='physical_exam_create'),
    path('encounters/<int:encounter_pk>/diagnosis/add/', views.DiagnosisCreateView.as_view(), name='diagnosis_create'),
    path('encounters/<int:encounter_pk>/treatment_plan/add/', views.TreatmentPlanCreateView.as_view(), name='treatment_plan_create'),
    path('encounters/<int:encounter_pk>/lab_request/add/', views.LabTestRequestCreateView.as_view(), name='lab_request_create'),
    path('lab_requests/<int:lab_request_pk>/result/add/', views.LabTestResultCreateView.as_view(), name='lab_result_create'),
    path('encounters/<int:encounter_pk>/imaging_request/add/', views.ImagingRequestCreateView.as_view(), name='imaging_request_create'),
    path('imaging_requests/<int:imaging_request_pk>/result/add/', views.ImagingResultCreateView.as_view(), name='imaging_result_create'),
    path('encounters/<int:encounter_pk>/prescription/add/', views.PrescriptionCreateView.as_view(), name='prescription_create'),

    # Doctor-specific URLs
    path('doctor/my_patients/', views.DoctorPatientListView.as_view(), name='doctor_patient_list'),

    # Logs
    path('activity-logs/', views.ActivityLogListView.as_view(), name='activity_log_list'),

    # Add URLs for other models (e.g., Appointments, Labs, Imaging, etc.) as needed
    # For instance:
    # path('appointments/', views.AppointmentListView.as_view(), name='appointment_list'),
    # path('appointments/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
]