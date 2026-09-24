from django.urls import path
from .employee_views import (
    PrivilegeCatalogView, RoleListCreateView, RoleDeleteView,
    EmployeeListCreateView, EmployeePrivilegesView, EmployeeDeactivateView,
    EmployeeBulkDeactivateView, EmployeeBulkActivateView, EmployeeBulkDeleteView, EmployeeResetPasswordView,
    EmployeeEmailView, AccountProfileView, AccountChangePasswordView,
)

urlpatterns = [
    path('privileges/', PrivilegeCatalogView.as_view(), name='privilege-catalog'),
    path('roles/', RoleListCreateView.as_view(), name='role-list-create'),
    path('roles/<int:role_id>/', RoleDeleteView.as_view(), name='role-delete'),
    path('employees/', EmployeeListCreateView.as_view(), name='employee-list-create'),
    path('employees/bulk-deactivate/', EmployeeBulkDeactivateView.as_view(), name='employee-bulk-deactivate'),
    path('employees/bulk-activate/', EmployeeBulkActivateView.as_view(), name='employee-bulk-activate'),  
    path('employees/bulk-delete/', EmployeeBulkDeleteView.as_view(), name='employee-bulk-delete'),
    path('employees/<int:employee_id>/privileges/', EmployeePrivilegesView.as_view(), name='employee-privileges'),
    path('employees/<int:employee_id>/deactivate/', EmployeeDeactivateView.as_view(), name='employee-deactivate'),
    path('employees/<int:employee_id>/reset-password/', EmployeeResetPasswordView.as_view(), name='employee-reset-password'),
    path('employees/<int:employee_id>/email/', EmployeeEmailView.as_view(), name='employee-email'),
    path('account/profile/', AccountProfileView.as_view(), name='account-profile'),
    path('account/change-password/', AccountChangePasswordView.as_view(), name='account-change-password'),
]