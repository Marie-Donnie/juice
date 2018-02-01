from enoslib.host import Host


def to_enos_roles(roles):
    """Transform the roles to use enoslib.host.Host hosts
    instead of dict
    
    :param roles: roles returned by deploy5k
    """

    def to_host(h):
        extra = {}
        # create extra_vars for the nics
        # network_role = ethX 
        for nic, roles in h["nics"]:
            for role in roles: 
                extra[role] = nic
        return Host(h["host"], user="root", extra=extra)

    enos_roles = {}
    for role, hosts in roles.items():
        enos_roles[role] = [to_host(h) for h in hosts]
    return enos_roles

