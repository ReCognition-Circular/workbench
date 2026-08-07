from django.urls import path

from checklists.views import (
    PhotoDeleteView,
    QRCodeView,
    TemplateListView,
    TemplateDetailView,
    DeviceChecklistView,
    DeviceInstanceListView,
    ChecklistCompleteView,
    ResponseUpdateView,
    PhotoUploadView,
    DevicePhotoListView,
)

urlpatterns = [
    # Templates
    path("templates/", TemplateListView.as_view(), name="checklist-templates"),
    path("templates/<str:code>/", TemplateDetailView.as_view(), name="checklist-template-detail"),

    # Device checklists
    path("devices/<int:pk>/checklists/", DeviceInstanceListView.as_view(), name="device-checklists"),
    path("devices/<int:pk>/checklists/<str:stage_code>/", DeviceChecklistView.as_view(), name="device-checklist"),
    path("devices/<int:pk>/checklists/<str:stage_code>/complete/", ChecklistCompleteView.as_view(), name="checklist-complete"),

    # Auto-save responses
    path("responses/<int:pk>/", ResponseUpdateView.as_view(), name="response-update"),

    # Photos
    path("photos/upload/", PhotoUploadView.as_view(), name="photo-upload"),
    path("devices/<int:pk>/photos/", DevicePhotoListView.as_view(), name="device-photos"),
    path("photos/<int:pk>/delete/", PhotoDeleteView.as_view(), name="photo-delete"),
    path("qr/", QRCodeView.as_view(), name="qr-code"),
]
