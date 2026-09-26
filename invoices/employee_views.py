from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status

from .models import StaffProfile, Role
from .serializers import EmployeeSerializer, RoleSerializer
from .permissions import has_permission
from .privileges import PRIVILEGE_CATALOG, PRIVILEGE_KEYS


def _clean_email(raw, exclude_user_id=None):
    """Returns (email, error). Empty is allowed (that employee just can't use Google)."""
    email = (raw or '').strip().lower()
    if not email:
        return '', None
    try:
        validate_email(email)
    except ValidationError:
        return None, 'Enter a valid email address.'
    qs = User.objects.filter(email__iexact=email)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    if qs.exists():
        return None, 'Another employee already uses that email.'
    return email, None


class PrivilegeCatalogView(APIView):
    """GET /api/privileges/ — the 11-item grid definition, so frontend never hardcodes it."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PRIVILEGE_CATALOG)


class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = Role.objects.all().order_by('name')
        return Response(RoleSerializer(roles, many=True).data)

    def post(self, request):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can create roles.'}, status=http_status.HTTP_403_FORBIDDEN)

        name = request.data.get('name', '').strip()
        privileges = request.data.get('defaultPrivileges', [])
        if not name:
            return Response({'error': 'Role name is required.'}, status=http_status.HTTP_400_BAD_REQUEST)
        if Role.objects.filter(name__iexact=name).exists():
            return Response({'error': 'A role with that name already exists.'}, status=http_status.HTTP_400_BAD_REQUEST)
        invalid = set(privileges) - PRIVILEGE_KEYS
        if invalid:
            return Response({'error': f'Unknown privilege keys: {invalid}'}, status=http_status.HTTP_400_BAD_REQUEST)

        role = Role.objects.create(name=name, defaultPrivileges=privileges, isBuiltIn=False)
        return Response(RoleSerializer(role).data, status=http_status.HTTP_201_CREATED)


class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profiles = StaffProfile.objects.select_related('user', 'role').order_by('user__username')
        return Response(EmployeeSerializer(profiles, many=True).data)

    def post(self, request):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can create employees.'}, status=http_status.HTTP_403_FORBIDDEN)

        full_name = request.data.get('fullName', '').strip()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        role_id = request.data.get('roleId')
        privileges = request.data.get('privileges')
        email = request.data.get('email', '')

        if not (full_name and username and password and role_id):
            return Response({'error': 'Full name, username, password, and role are required.'}, status=http_status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({'error': 'That username is already taken.'}, status=http_status.HTTP_400_BAD_REQUEST)
        email, email_error = _clean_email(email)
        if email_error:
            return Response({'error': email_error}, status=http_status.HTTP_400_BAD_REQUEST)
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response({'error': 'Invalid role.'}, status=http_status.HTTP_400_BAD_REQUEST)

        first, *rest = full_name.split(' ', 1)
        user = User.objects.create_user(username=username, password=password, email=email, first_name=first, last_name=rest[0] if rest else '')

        final_privileges = privileges if privileges is not None else role.defaultPrivileges
        invalid = set(final_privileges) - PRIVILEGE_KEYS
        if invalid:
            user.delete()
            return Response({'error': f'Unknown privilege keys: {invalid}'}, status=http_status.HTTP_400_BAD_REQUEST)

        profile = StaffProfile.objects.create(
            user=user, role=role, privileges=final_privileges,
            isActive=True, lastPasswordChange=timezone.now(),
        )
        return Response(EmployeeSerializer(profile).data, status=http_status.HTTP_201_CREATED)


class EmployeePrivilegesView(APIView):
    """PATCH /api/employees/<id>/privileges/ — update one user's effective privileges directly."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, employee_id):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can edit privileges.'}, status=http_status.HTTP_403_FORBIDDEN)

        try:
            profile = StaffProfile.objects.get(id=employee_id)
        except StaffProfile.DoesNotExist:
            return Response({'error': 'Employee not found.'}, status=http_status.HTTP_404_NOT_FOUND)

        privileges = request.data.get('privileges', [])
        invalid = set(privileges) - PRIVILEGE_KEYS
        if invalid:
            return Response({'error': f'Unknown privilege keys: {invalid}'}, status=http_status.HTTP_400_BAD_REQUEST)

        profile.privileges = privileges
        profile.save(update_fields=['privileges'])
        return Response(EmployeeSerializer(profile).data)


class EmployeeDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can deactivate employees.'}, status=http_status.HTTP_403_FORBIDDEN)
        try:
            profile = StaffProfile.objects.get(id=employee_id)
        except StaffProfile.DoesNotExist:
            return Response({'error': 'Employee not found.'}, status=http_status.HTTP_404_NOT_FOUND)

        profile.isActive = not profile.isActive
        profile.save(update_fields=['isActive'])
        profile.user.is_active = profile.isActive
        profile.user.save(update_fields=['is_active'])
        return Response(EmployeeSerializer(profile).data)

class EmployeeBulkDeactivateView(APIView):
    """POST /api/employees/bulk-deactivate/ — {employeeIds: [...]}. Always sets isActive=False."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can deactivate employees.'}, status=http_status.HTTP_403_FORBIDDEN)
        ids = request.data.get('employeeIds', [])
        profiles = StaffProfile.objects.filter(id__in=ids)
        if profiles.filter(user_id=request.user.id).exists():
            return Response({'error': "You can't deactivate your own account."}, status=http_status.HTTP_400_BAD_REQUEST)
        n = 0
        for profile in profiles:
            profile.isActive = False
            profile.save(update_fields=['isActive'])
            profile.user.is_active = False
            profile.user.save(update_fields=['is_active'])
            n += 1
        return Response({'deactivated': n})

class EmployeeBulkActivateView(APIView):
    """POST /api/employees/bulk-activate/ — {employeeIds: [...]}. Always sets isActive=True."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can activate employees.'}, status=http_status.HTTP_403_FORBIDDEN)
        ids = request.data.get('employeeIds', [])
        profiles = StaffProfile.objects.filter(id__in=ids)
        n = 0
        for profile in profiles:
            profile.isActive = True
            profile.save(update_fields=['isActive'])
            profile.user.is_active = True
            profile.user.save(update_fields=['is_active'])
            n += 1
        return Response({'activated': n})
class EmployeeBulkDeleteView(APIView):
    """POST /api/employees/bulk-delete/ — {employeeIds: [...]}. Hard-deletes the User row
    (StaffProfile cascades with it)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can delete employees.'}, status=http_status.HTTP_403_FORBIDDEN)
        ids = request.data.get('employeeIds', [])
        profiles = StaffProfile.objects.filter(id__in=ids)
        user_ids = list(profiles.values_list('user_id', flat=True))
        if request.user.id in user_ids:
            return Response({'error': "You can't delete your own account."}, status=http_status.HTTP_400_BAD_REQUEST)
        count = len(user_ids)
        User.objects.filter(id__in=user_ids).delete()
        return Response({'deleted': count})


class EmployeeResetPasswordView(APIView):
    """POST /api/employees/<id>/reset-password/ — admin sets a new password for any employee
    without needing the old one. Uses set_password() so it's actually hashed."""
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can reset passwords.'}, status=http_status.HTTP_403_FORBIDDEN)
        try:
            profile = StaffProfile.objects.get(id=employee_id)
        except StaffProfile.DoesNotExist:
            return Response({'error': 'Employee not found.'}, status=http_status.HTTP_404_NOT_FOUND)

        new_password = request.data.get('newPassword', '')
        if len(new_password) < 6:
            return Response({'error': 'New password must be at least 6 characters.'}, status=http_status.HTTP_400_BAD_REQUEST)

        profile.user.set_password(new_password)
        profile.user.save()
        profile.lastPasswordChangedBy = request.user
        profile.lastPasswordChange = timezone.now()
        profile.save(update_fields=['lastPasswordChangedBy', 'lastPasswordChange'])
        return Response(EmployeeSerializer(profile).data)


class EmployeeEmailView(APIView):
    """PATCH /api/employees/<id>/email/ {email}: admin sets the email used for Google sign-in."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, employee_id):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can edit emails.'}, status=http_status.HTTP_403_FORBIDDEN)
        try:
            profile = StaffProfile.objects.select_related('user').get(id=employee_id)
        except StaffProfile.DoesNotExist:
            return Response({'error': 'Employee not found.'}, status=http_status.HTTP_404_NOT_FOUND)
        email, err = _clean_email(request.data.get('email'), exclude_user_id=profile.user_id)
        if err:
            return Response({'error': err}, status=http_status.HTTP_400_BAD_REQUEST)
        profile.user.email = email
        profile.user.save(update_fields=['email'])
        return Response(EmployeeSerializer(profile).data)


class RoleDeleteView(APIView):
    """DELETE /api/roles/<id>/ — only custom (non-built-in) roles, and only if no employee
    currently uses it. Prevent-deletion, not reassignment, so nobody's privileges silently
    change underneath them."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, role_id):
        if not has_permission(request.user, 'manage_users'):
            return Response({'error': 'Only administrators can delete roles.'}, status=http_status.HTTP_403_FORBIDDEN)
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response({'error': 'Role not found.'}, status=http_status.HTTP_404_NOT_FOUND)
        if role.isBuiltIn:
            return Response({'error': 'Built-in roles cannot be deleted.'}, status=http_status.HTTP_400_BAD_REQUEST)
        in_use = role.staff.count()
        if in_use:
            return Response(
                {'error': f'{in_use} employee(s) still use this role. Reassign them to a different role first.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        role.delete()
        return Response({'success': True})


class AccountProfileView(APIView):
    """PATCH /api/account/profile/ — self-service display name / username edit for the
    logged-in user. Tracks who changed the username (always self here)."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        display_name = request.data.get('displayName', '').strip()
        new_username = request.data.get('username', '').strip()

        if display_name:
            first, *rest = display_name.split(' ', 1)
            user.first_name = first
            user.last_name = rest[0] if rest else ''

        if new_username and new_username != user.username:
            if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                return Response({'error': 'That username is already taken.'}, status=http_status.HTTP_400_BAD_REQUEST)
            user.username = new_username
            if hasattr(user, 'profile'):
                user.profile.lastUsernameChangedBy = user
                user.profile.lastUsernameChange = timezone.now()
                user.profile.save(update_fields=['lastUsernameChangedBy', 'lastUsernameChange'])

        user.save()
        return Response({'username': user.get_username(), 'displayName': user.get_full_name() or user.get_username()})


class AccountChangePasswordView(APIView):
    """PATCH /api/account/change-password/ — self-service password change. Requires the
    current password and actually hashes the new one via set_password()."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        old_password = request.data.get('oldPassword', '')
        new_password = request.data.get('newPassword', '')

        if not old_password or not new_password:
            return Response({'error': 'Current and new password are required.'}, status=http_status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({'error': 'Current password is incorrect.'}, status=http_status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 6:
            return Response({'error': 'New password must be at least 6 characters.'}, status=http_status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        if hasattr(user, 'profile'):
            user.profile.lastPasswordChangedBy = user
            user.profile.lastPasswordChange = timezone.now()
            user.profile.save(update_fields=['lastPasswordChangedBy', 'lastPasswordChange'])

        return Response({'success': True})