/**
 * Sistema de validación en tiempo real para formularios
 */

document.addEventListener('DOMContentLoaded', function() {
    const maxInputLength = 20;
    const limpiarTexto = function(input, patron) {
        const valorLimpio = Array.from(input.value).filter(function(caracter) {
            return patron.test(caracter);
        }).join('');
        if (input.value !== valorLimpio) {
            input.value = valorLimpio;
        }
    };

    document.querySelectorAll('[data-plain-text]').forEach(function(input) {
        input.addEventListener('input', function() {
            limpiarTexto(input, /[\p{L}\p{N}\s]/u);
        });
    });

    document.querySelectorAll('[data-person-name]').forEach(function(input) {
        input.addEventListener('input', function() {
            limpiarTexto(input, /[\p{L}\s]/u);
        });
    });

    document.querySelectorAll('[data-rut]').forEach(function(input) {
        input.addEventListener('input', function() {
            input.value = input.value.replace(/[^0-9Kk-]/g, '');
        });
    });

    // Configuración de validadores por tipo de campo
    const validators = {
        presupuesto: {
            validate: function(value) {
                if (value === '' || value === null) {
                    return { 
                        valid: false, 
                        message: 'El presupuesto es requerido' 
                    };
                }
                const numValue = parseFloat(value);
                if (isNaN(numValue)) {
                    return { 
                        valid: false, 
                        message: 'El presupuesto debe ser un número válido' 
                    };
                }
                if (numValue <= 0) {
                    return { 
                        valid: false, 
                        message: 'El presupuesto debe ser mayor que 0' 
                    };
                }
                return { valid: true };
            },
            pattern: /^-?\d+(\.\d{1,2})?$/
        },
        horas_diarias: {
            validate: function(value) {
                if (value === '') {
                    return {
                        valid: false,
                        message: 'Las horas diarias deben estar entre 1 y 8 horas.'
                    };
                }
                const numValue = Number(value);
                if (!Number.isFinite(numValue) || numValue < 1 || numValue > 8) {
                    return {
                        valid: false,
                        message: 'Las horas diarias deben estar entre 1 y 8 horas.'
                    };
                }
                return { valid: true };
            }
        },
        username: {
            validate: function(value) {
                if (!/^[0-9]{7,8}-[0-9Kk]$/.test(value.trim())) {
                    return { valid: false, message: 'Ingresa un RUT válido con formato 12345678-9.' };
                }
                return { valid: true };
            }
        },
        nombre: {
            validate: function(value) {
                if (value.trim() === '') {
                    return { 
                        valid: false, 
                        message: 'El nombre es requerido' 
                    };
                }
                if (value.trim().length < 3) {
                    return { 
                        valid: false, 
                        message: 'El nombre debe tener al menos 3 caracteres' 
                    };
                }
                return { valid: true };
            }
        },
        nombre_trabajador: {
            validate: function(value) {
                if (!/^[\p{L}]+(?:\s+[\p{L}]+)*$/u.test(value.trim())) {
                    return { valid: false, message: 'Solo se permiten letras y espacios.' };
                }
                return { valid: true };
            }
        },
        apellido_trabajador: {
            validate: function(value) {
                if (!/^[\p{L}]+(?:\s+[\p{L}]+)*$/u.test(value.trim())) {
                    return { valid: false, message: 'Solo se permiten letras y espacios.' };
                }
                return { valid: true };
            }
        },
        cliente: {
            validate: function(value) {
                if (value.trim() === '') {
                    return { 
                        valid: false, 
                        message: 'El cliente es requerido' 
                    };
                }
                return { valid: true };
            }
        },
        direccion: {
            validate: function(value) {
                if (value.trim() === '') {
                    return { 
                        valid: false, 
                        message: 'La dirección es requerida' 
                    };
                }
                return { valid: true };
            }
        },
        ciudad: {
            validate: function(value) {
                if (value.trim() === '') {
                    return { 
                        valid: false, 
                        message: 'La ciudad es requerida' 
                    };
                }
                return { valid: true };
            }
        },
        fecha_inicio: {
            validate: function(value) {
                if (value === '') {
                    return { 
                        valid: false, 
                        message: 'La fecha de inicio es requerida' 
                    };
                }
                // Comparar directamente strings en formato YYYY-MM-DD
                const today = new Date();
                const todayString = today.getFullYear() + '-' + 
                                   String(today.getMonth() + 1).padStart(2, '0') + '-' + 
                                   String(today.getDate()).padStart(2, '0');
                
                if (value < todayString) {
                    return { 
                        valid: false, 
                        message: 'La fecha de inicio no puede ser anterior al día actual' 
                    };
                }
                return { valid: true };
            }
        },
        fecha_termino: {
            validate: function(value) {
                if (value === '') return { valid: true };
                
                // Comparar directamente strings en formato YYYY-MM-DD
                const today = new Date();
                const todayString = today.getFullYear() + '-' + 
                                   String(today.getMonth() + 1).padStart(2, '0') + '-' + 
                                   String(today.getDate()).padStart(2, '0');
                
                if (value < todayString) {
                    return { 
                        valid: false, 
                        message: 'La fecha de término no puede ser anterior al día actual' 
                    };
                }
                
                const inicioInput = document.querySelector('input[name="fecha_inicio"]');
                if (inicioInput && inicioInput.value) {
                    if (value < inicioInput.value) {
                        return { 
                            valid: false, 
                            message: 'La fecha de término no puede ser anterior a la fecha de inicio' 
                        };
                    }
                    const inicio = new Date(inicioInput.value + 'T00:00:00');
                    const termino = new Date(value + 'T00:00:00');
                    const diasProyecto = Math.round(
                        (termino - inicio) / (1000 * 60 * 60 * 24)
                    );
                    if (diasProyecto < 21) {
                        return {
                            valid: false,
                            message: 'El proyecto debe durar como mínimo 3 semanas.'
                        };
                    }
                }
                return { valid: true };
            }
        },
        fecha_inicio_jornada: {
            validate: function(value) {
                if (!value) return { valid: true };
                const today = new Date();
                const todayString = today.getFullYear() + '-' +
                    String(today.getMonth() + 1).padStart(2, '0') + '-' +
                    String(today.getDate()).padStart(2, '0');
                return value < todayString
                    ? { valid: false, message: 'La fecha de jornada no puede ser anterior a hoy.' }
                    : { valid: true };
            }
        },
        fecha_fin_jornada: {
            validate: function(value) {
                if (!value) return { valid: true };
                const inicioInput = document.querySelector('input[name="fecha_inicio_jornada"]');
                if (inicioInput && inicioInput.value && value < inicioInput.value) {
                    return { valid: false, message: 'El último día no puede ser anterior al primer día.' };
                }
                return { valid: true };
            }
        }
    };

    // Obtener todos los campos del formulario
    const formInputs = document.querySelectorAll('input[name], select[name], textarea[name]');
    
    formInputs.forEach(input => {
        const fieldName = input.name;
        
        // Crear contenedor para mensaje de error si no existe
        if (!input.parentElement.querySelector('.field-error')) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'field-error alert alert-danger d-none mt-2 mb-2 py-2 px-3';
            errorDiv.style.fontSize = '0.9rem';
            input.parentElement.appendChild(errorDiv);
        }

        // Agregar evento de validación en tiempo real
        input.addEventListener('blur', function() {
            validateField(input, fieldName, validators);
        });

        input.addEventListener('input', function() {
            const result = validateField(input, fieldName, validators);
            if (
                !result.valid &&
                Array.from(input.value).length > 20
            ) {
                showAlert(result.message, 'warning');
            }
        });

        input.addEventListener('change', function() {
            validateField(input, fieldName, validators);
        });
    });

    const fechaInicioProyecto = document.querySelector('input[name="fecha_inicio"]');
    const fechaTerminoProyecto = document.querySelector('input[name="fecha_termino"]');
    if (fechaInicioProyecto && fechaTerminoProyecto) {
        const actualizarMinimoTermino = function() {
            if (!fechaInicioProyecto.value) {
                fechaTerminoProyecto.removeAttribute('min');
                fechaTerminoProyecto.setCustomValidity('');
                return;
            }
            const inicio = new Date(fechaInicioProyecto.value + 'T00:00:00');
            inicio.setDate(inicio.getDate() + 21);
            const minimo = inicio.getFullYear() + '-' +
                String(inicio.getMonth() + 1).padStart(2, '0') + '-' +
                String(inicio.getDate()).padStart(2, '0');
            fechaTerminoProyecto.min = minimo;
            if (
                fechaTerminoProyecto.value &&
                fechaTerminoProyecto.value < minimo
            ) {
                fechaTerminoProyecto.setCustomValidity(
                    'El proyecto debe durar como mínimo 3 semanas.'
                );
            } else {
                fechaTerminoProyecto.setCustomValidity('');
            }
        };
        const validarTerminoProyecto = function() {
            actualizarMinimoTermino();
            const result = validateField(
                fechaTerminoProyecto,
                'fecha_termino',
                validators
            );
            if (!result.valid && fechaTerminoProyecto.value) {
                showAlert(result.message, 'warning');
            }
            fechaTerminoProyecto.setCustomValidity(
                result.valid ? '' : result.message
            );
        };
        fechaInicioProyecto.addEventListener('input', validarTerminoProyecto);
        fechaInicioProyecto.addEventListener('change', validarTerminoProyecto);
        fechaTerminoProyecto.addEventListener('input', validarTerminoProyecto);
        fechaTerminoProyecto.addEventListener('change', validarTerminoProyecto);
        fechaTerminoProyecto.addEventListener('blur', validarTerminoProyecto);
        actualizarMinimoTermino();
    }

    // Validar formulario antes de enviar
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            
            const inputs = form.querySelectorAll('input[name], select[name], textarea[name]');
            inputs.forEach(input => {
                const fieldName = input.name;
                const result = validateField(input, fieldName, validators);
                if (!result.valid) {
                    isValid = false;
                }
            });

            if (!isValid) {
                e.preventDefault();
                showAlert(
                    'Por favor, corrija los errores en el formulario',
                    'danger'
                );
            }
        });
    });
});

/**
 * Valida un campo individual
 * @param {HTMLElement} input - El elemento input a validar
 * @param {string} fieldName - Nombre del campo
 * @param {object} validators - Objeto con validadores
 * @returns {object} - {valid: boolean, message: string}
 */
function validateField(input, fieldName, validators) {
    const errorDiv = input.parentElement.querySelector('.field-error');
    let result = { valid: true };

    if (input.type !== 'hidden' && Array.from(input.value).length > getInputMaxLength(input)) {
        result = {
            valid: false,
            message: `Este campo no puede superar ${getInputMaxLength(input)} caracteres.`
        };
    }

    // Buscar validador para este campo
    if (result.valid && validators[fieldName]) {
        result = validators[fieldName].validate(input.value);
    }

    // Mostrar/ocultar error
    if (!result.valid) {
        if (errorDiv) {
            errorDiv.textContent = result.message;
            errorDiv.classList.remove('d-none');
        }
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
    } else {
        if (errorDiv) {
            errorDiv.classList.add('d-none');
        }
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
    }

    return result;
}

function getInputMaxLength(input) {
    return input.name === 'email' ? 40 : 20;
}

/**
 * Muestra una alerta en la página
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo de alerta (success, danger, warning, info)
 */
function showAlert(message, type = 'info') {
    const existingAlert = document.querySelector('[data-validation-alert]');
    if (existingAlert) {
        existingAlert.remove();
    }
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.dataset.validationAlert = 'true';
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const topContainer = document.querySelector('main, .login-wrapper');
    if (topContainer) {
        topContainer.insertBefore(alertDiv, topContainer.firstChild);
    }
}
