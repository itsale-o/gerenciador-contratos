from django import template

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