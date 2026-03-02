class ContratosRouter:
    def db_for_read(self, model, **hints):
        if model._meta.model_name == "contrato":
            return "contratos"
        return None
    
    def db_for_write(self, model, **hints):
        if model._meta.model_name == "contrato":
            return "contratos"
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name == "contrato":
            return False
        return None