from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.permissions import has_valid_employee_scope, role_home_name
from restaurant.models import Branch


class BembaLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        user = form.get_user()
        if not has_valid_employee_scope(user):
            form.add_error(None, 'Tu perfil no tiene una suscripción, restaurante o sucursal activa asignada.')
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        requested_url = self.get_redirect_url()
        if requested_url:
            return requested_url
        return reverse(role_home_name(self.request.user))


class BembaLogoutView(LogoutView):
    next_page = reverse_lazy('login')


def staff_roles_for(user):
    blocked_roles = {User.Role.ADMIN}
    if user.role == User.Role.MANAGER:
        blocked_roles.add(User.Role.MANAGER)
    return [choice for choice in User.Role.choices if choice[0] not in blocked_roles]


def can_manage_restaurant_staff(user):
    return (
        has_valid_employee_scope(user)
        and not user.is_superuser
        and user.role in [User.Role.ADMIN, User.Role.MANAGER]
    )


def branches_for(user):
    if user.role == User.Role.MANAGER:
        return Branch.objects.filter(pk=user.branch_id)
    return Branch.objects.filter(restaurant_id=user.restaurant_id)


def staff_queryset_for(user):
    queryset = User.objects.exclude(is_superuser=True)
    if user.role == User.Role.ADMIN:
        return queryset.filter(restaurant=user.restaurant).exclude(role=User.Role.ADMIN)
    return queryset.filter(branch=user.branch).exclude(
        role__in=[User.Role.ADMIN, User.Role.MANAGER]
    )


@login_required
def staff_list(request):

    if request.user.is_superuser:
        return HttpResponseRedirect('/admin/')
    if not can_manage_restaurant_staff(request.user):
        return render(
            request,
            'error.html',
            {'message': 'No tienes permiso para acceder aquí.'},
            status=403
        )

    users = staff_queryset_for(request.user)

    context = {
        'users': users.select_related('branch', 'restaurant'),
        'roles': staff_roles_for(request.user),
    }

    return render(
        request,
        'accounts/staff_list.html',
        context
    )


@login_required
def staff_create(request):
    """Crear nuevo empleado"""
    if not can_manage_restaurant_staff(request.user):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        role = request.POST.get('role', User.Role.WAITER)
        phone = request.POST.get('phone', '')
        allowed_roles = staff_roles_for(request.user)
        if role not in {value for value, _label in allowed_roles}:
            return render(request, 'accounts/staff_form.html', {
                'error': 'No tienes permiso para asignar ese rol.',
                'roles': allowed_roles,
                'branches': branches_for(request.user),
                'selected_branch_id': request.POST.get('branch'),
            }, status=403)
        if request.user.role == User.Role.MANAGER:
            branch = request.user.branch
        else:
            branch = get_object_or_404(
                branches_for(request.user), pk=request.POST.get('branch')
            )
        
        # Validación básica
        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/staff_form.html', {
                'error': 'El nombre de usuario ya existe.',
                'roles': allowed_roles,
                'branches': branches_for(request.user),
                'selected_branch_id': request.POST.get('branch'),
            })
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role,
            phone=phone,
            restaurant=request.user.restaurant,
            branch=branch,
            is_active_employee=True,
        )
        return HttpResponseRedirect(reverse_lazy('staff_list'))
    
    return render(request, 'accounts/staff_form.html', {
        'roles': staff_roles_for(request.user),
        'branches': branches_for(request.user),
        'selected_branch_id': request.user.branch_id,
    })


@login_required
def staff_edit(request, pk):
    """Editar empleado"""
    if not can_manage_restaurant_staff(request.user):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        staff_queryset_for(request.user),
        pk=pk
    )
    
    if request.method == 'POST':
        requested_role = request.POST.get('role', user.role)
        allowed_roles = staff_roles_for(request.user)
        if requested_role not in {value for value, _label in allowed_roles}:
            return render(request, 'accounts/staff_form.html', {
                'error': 'No tienes permiso para asignar ese rol.',
                'roles': allowed_roles,
                'branches': branches_for(request.user),
                'selected_branch_id': request.POST.get('branch'),
                'user': user,
                'is_edit': True,
            }, status=403)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.role = requested_role
        if request.user.role == User.Role.MANAGER:
            user.branch = request.user.branch
        else:
            user.branch = get_object_or_404(
                branches_for(request.user), pk=request.POST.get('branch')
            )
        user.is_active_employee = request.POST.get('is_active_employee') == 'on'
        
        password = request.POST.get('password')
        if password:
            user.set_password(password)
        
        user.save()
        return HttpResponseRedirect(reverse_lazy('staff_list'))
    
    return render(request, 'accounts/staff_form.html', {
        'user': user,
        'roles': staff_roles_for(request.user),
        'branches': branches_for(request.user),
        'selected_branch_id': user.branch_id,
        'is_edit': True,
    })


@login_required
@require_POST
def staff_delete(request, pk):
    """Eliminar empleado (desactivar)"""
    if not can_manage_restaurant_staff(request.user):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        staff_queryset_for(request.user),
        pk=pk
    )
    
    user.is_active_employee = False
    user.save(update_fields=['is_active_employee'])
    
    return HttpResponseRedirect(reverse_lazy('staff_list'))


@login_required
@require_POST
def staff_activate(request, pk):
    """Activar empleado"""
    if not can_manage_restaurant_staff(request.user):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        staff_queryset_for(request.user),
        pk=pk
    )
    
    user.is_active_employee = True
    user.save(update_fields=['is_active_employee'])
    
    return HttpResponseRedirect(reverse_lazy('staff_list'))

