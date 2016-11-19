import itertools
    
# Run a system of pool_size processes on the given method
def run(pool_size, main_loop, method):
    # Create a context for sending messages to bots and sockets
    context = Context(pool_size)
    # Initialize processes
    processes = [method(context, i) for i in xrange(0, pool_size)]
    # Return the first element generated by main_loop that is not null
    return next(itertools.dropwhile(lambda _: _ == None, main_loop(context, processes)))

# Main loop: run processes and manage messages
def main_loop(context, processes):
    # Remove messages matching a filter from the message queues
    def _discard_messages(filter):
        for queue in context.message_queues:
            queue[:] = (msg for msg in queue if not filter(msg))
    # Add messages from the temporary message queues to the message queues
    def _dequeue_tmp_message_queues():
        context.message_queues[:] = (context.message_queues[i] + context.tmp_message_queues[i] for i in xrange(0, context.pool_size))
        context.tmp_message_queues[:] = ([] for i in xrange(0, context.pool_size))
    # Main loop
    while any(processes):
        # Allow decorators to do a pre processing before next loop
        yield
        # Run the next step
        processes[:] = (process if process and not next(process) else None for process in processes)
        # Discard all read messages from queues
        _discard_messages(lambda msg: msg["read"])
        # Process messages from temporary message queues
        _dequeue_tmp_message_queues()
        # Allow decorators to do a post processing before next loop
        yield
    # Done
    yield True

# Context allowing for processes to know about the system and interact together
class Context(dict):
    def __init__(self, pool_size):
        super(Context, self).__init__()
        self["pool_size"] = pool_size
        self["tmp_message_queues"] = [[] for _ in xrange(0, pool_size)]
        self["message_queues"] = [[] for _ in xrange(0, pool_size)]
        self["groups"] = {}
        
    def __getattr__(self, attr):
        return self[attr]
    
    def __setattr__(self, attr, value):
        self[attr] = value

# Return all received messages matching a filter
def _messages(context, receiver, filter):
    return (msg for msg in context.message_queues[receiver] if not msg["read"] and filter(msg))
    
# Send a message to all elements in receivers
def send(context, sender, receivers, message):
    for receiver in receivers:
        context.tmp_message_queues[receiver].append({
            "sender": sender,
            "message": message,
            "read": False
        })
        yield receiver

# Return and mark as read all received messages matching a filter
def recv(context, receiver, filter):
    for msg in _messages(context, receiver, filter):
        msg["read"] = True
        yield msg
        
# Indicate if a message matching a filter has been received
def has_message(context, receiver, filter):
    return len([_ for _ in _messages(context, receiver, filter)]) != 0
    
# Send filter: send to all processes in the pool
def send_all(context, sender):
    return (_ for _ in xrange(0, context.pool_size) if _ != sender)
        
# Send filter: send to all processes in a group
def send_group(context, sender, group):
    return (_ for _ in get_group_processes(context, group) if _ != sender)

# Send filter: send to all processes in a list
def send_to(context, sender, *args):
    return (_ for _ in args if _ != sender)
        
# Recv filter: receive from all processes in the pool
def recv_all():
    return lambda message: True
    
# Recv filter: receive from all processes in a list
def recv_from(*args):
    def _recv_from(message):
        return message["sender"] in args
    return _recv_from

# Get all processes in a group
def get_group_processes(context, group):
    return (_ for _ in context.groups[group]) if group in context.groups else ()
        
# Groups
def join(context, process, group):
    context.groups.setdefault(group, set()).add(process)
        
def leave(context, process, group):
    groups = context.groups
    if groups.has_key(group):
        groups[group].remove(process)
        if len(groups[group]) == 0:
            del groups[group]