from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from accounts.models import User
from restaurant.tenancy import scoped_queryset


class BembaLoginView(LoginView):
    template_name = 'accounts/login.html'


class BembaLogoutView(LogoutView):
    next_page = reverse_lazy('login')


@login_required
def staff_list(request):
    """Listar empleados del restaurante del usuario"""
    if not request.user.has_role('admin', 'manager'):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    users = scoped_queryset(User.objects.all(), request.user).exclude(is_superuser=True).select_related('branch')
    
    context = {
        'users': users,
        'roles': User.Role.choices,
    }
    return render(request, 'accounts/staff_list.html', context)


@login_required
def staff_create(request):
    """Crear nuevo empleado"""
    if not request.user.has_role('admin', 'manager'):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        role = request.POST.get('role', User.Role.WAITER)
        phone = request.POST.get('phone', '')
        
        # Validación básica
        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/staff_form.html', {
                'error': 'El nombre de usuario ya existe.',
                'roles': User.Role.choices,
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
            branch=request.user.branch,
            is_active_employee=True,
        )
        return HttpResponseRedirect(reverse_lazy('staff_list'))
    
    return render(request, 'accounts/staff_form.html', {
        'roles': User.Role.choices,
    })


@login_required
def staff_edit(request, pk):
    """Editar empleado"""
    if not request.user.has_role('admin', 'manager'):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        scoped_queryset(User.objects.all(), request.user),
        pk=pk
    )
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.role = request.POST.get('role', user.role)
        user.is_active_employee = request.POST.get('is_active_employee') == 'on'
        
        password = request.POST.get('password')
        if password:
            user.set_password(password)
        
        user.save()
        return HttpResponseRedirect(reverse_lazy('staff_list'))
    
    return render(request, 'accounts/staff_form.html', {
        'user': user,
        'roles': User.Role.choices,
        'is_edit': True,
    })


@login_required
@require_POST
def staff_delete(request, pk):
    """Eliminar empleado (desactivar)"""
    if not request.user.has_role('admin', 'manager'):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        scoped_queryset(User.objects.all(), request.user),
        pk=pk
    )
    
    user.is_active_employee = False
    user.save(update_fields=['is_active_employee'])
    
    return HttpResponseRedirect(reverse_lazy('staff_list'))


@login_required
@require_POST
def staff_activate(request, pk):
    """Activar empleado"""
    if not request.user.has_role('admin', 'manager'):
        return render(request, 'error.html', {'message': 'No tienes permiso para acceder aquí.'}, status=403)
    
    user = get_object_or_404(
        scoped_queryset(User.objects.all(), request.user),
        pk=pk
    )
    
    user.is_active_employee = True
    user.save(update_fields=['is_active_employee'])
    
    return HttpResponseRedirect(reverse_lazy('staff_list'))

