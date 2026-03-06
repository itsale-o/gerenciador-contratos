class ContratosRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == "contratos":
            return "contratos"
        return "default"
    
    def db_for_write(self, model, **hints):
        if model._meta.app_label == "contratos":
            return "contratos"
        return "default"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "contratos":
            return False
        if db == "default":
            return True

        return None