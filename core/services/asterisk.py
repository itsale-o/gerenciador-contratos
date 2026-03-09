from asterisk.manager import Manager

ASTERISK_HOST = "177.107.94.9"
ASTERISK_PORT = 5038
ASTERISK_USER = "admin"
ASTERISK_SECRET = "1125Xan4185"

def get_manager():
    manager = Manager()
    manager.connect(ASTERISK_HOST, ASTERISK_PORT)
    manager.login(ASTERISK_USER, ASTERISK_SECRET)
    return manager

def make_call(ramal, numero):
    try:
        manager = get_manager()

        response = manager.originate(
            channel=f"PJSIP/{ramal}",
            exten=numero,
            context="from-internal",
            priority=1,
            caller_id="Sistema Django"
        )

        manager.close()

        if response.response == "Success":
            return True
    except Exception as e:
        print(e)

    return False

def ami_listener():
    manager = Manager()
    manager.connect("177.107.94.9", 5038)
    manager.login("admin", "1125Xan4185")

    def handle_event(event, manager):
        print(event.name)

        if event.name == "DialEnd":
            status = event.headers.get("DialStatus")
            print("Status da chamada:", status)
    
    manager.register_event("*", handle_event)
    manager.event_dispatch()