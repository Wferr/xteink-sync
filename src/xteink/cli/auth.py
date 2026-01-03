"""Authentication commands for xteink CLI."""

import getpass


def login(args, client):
    """Login to Xteink cloud"""
    email = args.email or input("Email address: ")
    password = args.password or getpass.getpass("Password: ")
    try:
        result = client.login(email, password)
        print("\033[92mLogin successful!\033[0m")
        print(f"User ID: {result.user_id}")
        print("Tokens saved to ~/.xteink/tokens.json")
    except Exception as e:
        print(f"\033[91mLogin failed: {str(e)}\033[0m")


def register(args, client):
    """Register a new account"""
    email = args.email or input("Email address: ")
    nickname = args.nickname or input("Nickname: ")
    password = args.password or getpass.getpass("Password: ")
    try:
        # Step 1: Send verification code
        print(f"Sending verification code to {email}...")
        client.send_verification_code(email)
        print("\033[92mVerification code sent!\033[0m")

        # Step 2: Get code
        code = input("Enter verification code: ")

        # Step 3: Register
        print("Registering...")
        result = client.register(email, nickname, password, code)

        print("\033[92mRegistration successful!\033[0m")
        print(f"Welcome, {result.user.nickname}!")
        print(f"User ID: {result.user.id}")
        print(f"Message: {result.message}")
        print("Tokens saved to ~/.xteink/tokens.json")

    except Exception as e:
        print(f"\033[91mRegistration failed: {str(e)}\033[0m")


def logout(args, client):
    """Logout and clear local tokens"""
    try:
        result = client.logout()
        print(f"\033[92m{result.message}\033[0m")
    except Exception as e:
        print(f"\033[91mLogout failed: {str(e)}\033[0m")


def refresh(args, client):
    """Refresh access token"""
    try:
        client.refresh_access_token()
        print("\033[92mToken refreshed successfully!\033[0m")
    except Exception as e:
        print(f"\033[91mToken refresh failed: {str(e)}\033[0m")


def status(args, client):
    """Check connectivity, API health, and authentication status"""
    server_url = client.BASE_URL
    print(f"Target Server: {server_url}")

    # 1. Check connectivity & API Health
    try:
        health = client.get_health()
        status_str = health.status.upper()
        if health.status == "healthy":
            status_str = f"\033[92m{status_str}\033[0m"
        else:
            status_str = f"\033[93m{status_str}\033[0m"
        print(f"API Status: {status_str}")
        print(f"Message: {health.message}")
    except Exception as e:
        print(f"\033[91mConnection Failed: {str(e)}\033[0m")
        return

    # 2. Check authentication
    if client.is_authenticated():
        try:
            # Try a lightweight authenticated request to verify the token
            client.get_device_binding()
            print("\033[92mAuthentication: VALID\033[0m")
            print(f"User ID: {client.user_id}")
        except Exception as e:
            # If it fails, try to refresh if we have a refresh token
            if client.refresh_token:
                print("\033[93mToken expired, attempting refresh...\033[0m")
                try:
                    client.refresh_access_token()
                    print("\033[92mAuthentication: REFRESHED & VALID\033[0m")
                    print(f"User ID: {client.user_id}")
                except Exception as b_e:
                    print(f"\033[91mAuthentication Failed (Refresh failed): {str(b_e)}\033[0m")
            else:
                print(f"\033[91mAuthentication Failed (No refresh token): {str(e)}\033[0m")
    else:
        print("\033[93mAuthentication: None\033[0m")
        print("Run 'xteink auth login' to authenticate")
