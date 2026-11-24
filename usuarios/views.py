from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from .forms import RegistroUsuarioForm
from core.validators import validate_form_input_lengths


def registro_view(request):
    """
    Vista para el registro de nuevos usuarios.
    """
    if request.user.is_authenticated:
        # Si el usuario ya está autenticado, redirigir al dashboard
        return redirect('index')
    
    if request.method == 'POST':
        try:
            validate_form_input_lengths(request.POST, limits={"email": 40})
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('registro')
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Iniciar sesión automáticamente después del registro
            login(request, user)
            messages.success(
                request,
                f'✅ ¡Bienvenido {user.get_full_name() or user.username}! Tu cuenta ha sido creada exitosamente.'
            )
            return redirect('index')
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        form = RegistroUsuarioForm()
    
    return render(request, 'usuarios/registro.html', {'form': form})
