from django.conf import settings


class ContratosRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == "contratos":
            return "default" if settings.PROD else "contratos"
        return "default"
    
    def db_for_write(self, model, **hints):
        if model._meta.app_label == "contratos":
            return "default" if settings.PROD else "contratos"
        return "default"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "contratos":
            return False
        return db == "default"