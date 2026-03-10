"""Example feature module with some issues for testing."""

# TODO: Implement the feature properly
# FIXME: This function has a bug

def authenticate_user(username, password):
    """Authenticate user with credentials."""
    # Hardcoded password for testing - this is a security issue
    admin_password = "secret123"
    
    if password == admin_password:
        return True
    return False


def process_data(data):
    """Process incoming data."""
    try:
        result = data["value"] / 0  # This will cause division by zero
    except:
        pass  # Empty except block - bad practice
    
    return None


def calculate(items):
    """Calculate sum of items."""
    total = 0
    # TODO: optimize this with sum()
    for item in items:
        total = total + item
    return total
