import nipyapi
import logging
import urllib3
import time
 
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.getLogger('nipyapi.utils').setLevel(logging.INFO)
logging.getLogger('nipyapi.security').setLevel(logging.INFO)
logging.getLogger('nipyapi.versioning').setLevel(logging.INFO)
 
urllib3.disable_warnings()
 
nipyapi.config.nifi_config.host = 'https://NIFIHOST/nifi-api'
nipyapi.config.global_ssl_verify = False
nipyapi.config.nifi_config.verify_ssl = False
nipyapi.config.default_nifi_username = 'NIFIUSER'
nipyapi.config.default_nifi_password = 'NIFIPASSWORD'
 
name_to_id = {}
id_to_name = {}
 
 
def nifi_login():
    loggedin = False
    i = 0
    attempts = 3
    delay = 10
    while (i < attempts) and (loggedin is False):
        log.info("Logging in. Attempt: " + str(i))
        loggedin = nipyapi.security.service_login(bool_response=True)
        if loggedin is False:
            time.sleep(delay)
            i = i + 1
    return loggedin
 
 
def init_lookups():
    root_pg_id = nipyapi.canvas.get_root_pg_id()
 
    pg_list = nipyapi.canvas.list_all_process_groups(root_pg_id)
    for pg in pg_list:
        name_to_id[pg.component.name] = pg.id
        id_to_name[pg.id] = pg.component.name


def empty_queues(app):
    app_pg_groups = nipyapi.canvas.list_all_process_groups(name_to_id[app])
    # Empty queues
    for app_pg_group in app_pg_groups:
        log.info("Remove all messages on connection queues of: " + str(app_pg_group.component.name))
        for con in nipyapi.canvas.list_all_connections(app_pg_group.id,True):
            if (con.status.aggregate_snapshot.queued_count is not '0'):
                log.info("Empty queue: " + str(con.id))
                mycon = nipyapi.nifi.ConnectionsApi().get_connection(con.id)
                oldexp = mycon.component.flow_file_expiration
                mycon.component.flow_file_expiration = '1 sec'
                nipyapi.nifi.ConnectionsApi().update_connection(con.id, mycon)
                time.sleep(10)
                mycon.component.flow_file_expiration = oldexp
                nipyapi.nifi.ConnectionsApi().update_connection(con.id, mycon)
 
 
def disable_proc(app):
    app_pg_groups = nipyapi.canvas.list_all_process_groups(name_to_id[app])
    # Disable controllers, process groups and empty queues
    for app_pg_group in app_pg_groups:
        log.info("Disabling process group: " + str(app_pg_group.component.name))
        nipyapi.canvas.schedule_process_group(app_pg_group.id, False)
        log.info("Remove all messages on connection queues of: " + str(app_pg_group.component.name))
        nipyapi.canvas.purge_process_group(app_pg_group, stop=False)
        log.info("Disabling controllers for: " + str(app_pg_group.component.name))
        acse = nipyapi.nifi.ActivateControllerServicesEntity()
        acse.state = "DISABLED"
        acse.id = app_pg_group.id
        nipyapi.nifi.FlowApi().activate_controller_services(id=app_pg_group.id, body=acse)
 
 
def enable_proc(app):
    app_pg_groups = nipyapi.canvas.list_all_process_groups(name_to_id[app])
    # Enable controllers and process groups
    for app_pg_group in app_pg_groups:
        log.info("Enabling controllers for: " + str(app_pg_group.component.name))
        acse = nipyapi.nifi.ActivateControllerServicesEntity()
        acse.state = "ENABLED"
        acse.id = app_pg_group.id
        nipyapi.nifi.FlowApi().activate_controller_services(id=app_pg_group.id, body=acse)
        log.info("Enabling process group: " + str(app_pg_group.component.name))
        nipyapi.canvas.schedule_process_group(app_pg_group.id, True)
 
 
def get_unused_controller_services(app):
    app_pg = nipyapi.canvas.get_process_group(identifier_type='id',identifier=name_to_id[app])
    # Enable controllers and process groups
    cs = nipyapi.nifi.FlowApi().get_controller_services_from_group(id=app_pg.id, include_ancestor_groups=False, include_descendant_groups=True).controller_services
    for service in cs:
        if len(service.component.referencing_components)==0:
            print("Controller service " + str(service.component.name) + " has no referencing components. Parent pg: "+id_to_name[service.component.parent_group_id])
 
 
def get_unused_parameters(app):
    app_pg_groups = nipyapi.canvas.list_all_process_groups(name_to_id[app])
    # Enable controllers and process groups
    for pg in app_pg_groups:
        if (pg.parameter_context is not None):
            #print("Processing: "+ str(pg.parameter_context.component.name))
            param_context = nipyapi.nifi.ParameterContextsApi().get_parameter_context(pg.parameter_context.component.id)
            params=param_context.component.parameters
            for param in params:
                if len(param.parameter.referencing_components) == 0:
                    print("Context: " + str(pg.parameter_context.component.name)+". Parameter: " + str(param.parameter.name) + " is not being used")
                if param.parameter.sensitive is True and param.parameter.value is None:
                    print("Context: " + str(pg.parameter_context.component.name)+". Sensitive parameter " + str(param.parameter.name) + " has no value set")
         else:
             print("Process group: " + str(pg.component.name) + " has no parameter context assigned")
 
 
if __name__ == '__main__':
    log.info("Logged in: " + str(nifi_login()))
    init_lookups()
    #disable_proc("MyApp")
    #enable_proc("MyApp")
    get_unused_controller_services("MyApp")
    get_unused_parameters("MyApp")
