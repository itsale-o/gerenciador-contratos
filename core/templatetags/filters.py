from django import template
from django.utils.formats import number_format

register = template.Library()

@register.filter(name="bootstrap_alert_class")
def bootstrap_alert_class(tag):
    return "danger" if tag == "error" else tag


@register.filter(name="bootstrap_icon")
def bootstrap_icon(tag):
    icon_map = {
        "error": "bi-exclamation-triangle-fill",
        "success": "bi-check-circle-fill",
        "warning": "bi-exclamation-circle-fill",
        "info": "bi-info-circle-fill",
    }

    return icon_map.get(tag , "bi-info-circle-fill")

@register.filter(name="has_group")
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

@register.filter
def get_item(dicionario, chave):
    return dicionario.get(chave, [])

@register.filter
def moeda(valor):
    if valor is None:
        return "R$ 0,00"
    
    try:
        valor_formatado = number_format(valor, decimal_pos=2, use_l10n=True, force_grouping=True)

        if valor < 0:
            valor *= (-1)
            valor_formatado = number_format(valor, decimal_pos=2, use_l10n=True, force_grouping=True)
            
            return f"-R$ {valor_formatado}"
        return f"R$ {valor_formatado}"
    except (ValueError, TypeError):
        return valor