"""Launch a Lambda Labs cloud instance from environment settings."""

import os
import sys
import time

import requests


def get_and_validate_env_vars():
    """Get and validate required environment variables."""
    instance_type_name = os.getenv("INSTANCE_TYPE_NAME", "").lower()
    region_name = os.getenv("REGION_NAME", "").lower()
    ssh_key_names = os.getenv("SSH_KEY_NAMES")
    file_system_names = os.getenv("FILE_SYSTEM_NAMES")  # Optional
    name = os.getenv("NAME", "")  # Optional
    lambda_token = os.getenv("LAMBDA_TOKEN")

    required_env_vars = {
        "LAMBDA_TOKEN": lambda_token,
        "INSTANCE_TYPE_NAME": instance_type_name,
        "REGION_NAME": region_name
    }

    for var_name, var_value in required_env_vars.items():
        if not var_value:
            raise ValueError(f"{var_name} environment variable is not set")

    if ssh_key_names:
        ssh_key_names = ssh_key_names.split(",")
    else:
        raise ValueError("SSH_KEY_NAMES environment variable is not set")

    if file_system_names:
        file_system_names = file_system_names.split(",")
    else:
        file_system_names = []

    instance_params = {
        "instance_type_name": instance_type_name,
        "region_name": region_name,
        "ssh_key_names": ssh_key_names,
        "file_system_names": file_system_names,
        "name": name,
    }

    return instance_params, lambda_token


def launch_instance(instance_params, lambda_token):
    """Launch the instance and return the response."""
    url = "https://cloud.lambdalabs.com/api/v1/instance-operations/launch"
    headers = {"Authorization": f"Bearer {lambda_token}"}

    response = requests.post(
        url,
        headers=headers,
        json=instance_params,
        timeout=300,
    )

    return response


def handle_response(response):
    """Handle the response from the instance launch."""
    if response.status_code != 200:
        error = response.json().get("error", {"message": "An unknown error occurred"})
        print(
            f'Error code: {response.status_code}, {error.get("code", "global/unknown")}'
            f'Message: {error["message"]}'
            f'Suggestion: {error.get("suggestion", "No suggestion available")}'
        )
        sys.exit(1)

    # Get data/instance_ids from response
    data = response.json().get("data", {})
    instance_id = data.get("instance_ids", [])[0]

    # Get the path to the GITHUB_OUTPUT environment file
    output_file_path = os.getenv("GITHUB_OUTPUT")

    # Write the output to the GITHUB_OUTPUT environment file
    if output_file_path is not None:
        with open(output_file_path, "a", encoding="utf-8") as file:
            file.write(f"instance_id={instance_id}\n")
    else:
        raise ValueError("GITHUB_OUTPUT environment variable is not set.")

    return instance_id


def wait_for_boot(instance_id, lambda_token):
    """Wait for the instance to boot."""
    if not os.getenv("WAIT_FOR_BOOT", "false") == "true":
        return

    timeout = int(os.getenv("BOOT_TIMEOUT", "300"))
    start_time = time.time()
    url = f"https://cloud.lambdalabs.com/api/v1/instances/{instance_id}"
    headers = {"Authorization": f"Bearer {lambda_token}"}

    while True:
        response = requests.get(url, headers=headers, timeout=10)
        instance_status = response.json().get("data", {}).get("status")
        if instance_status != "booting":
            break
        if time.time() - start_time > timeout:
            raise TimeoutError("Instance boot timeout reached.")
        time.sleep(5)  # Sleep for a short period before retrying

    # Status is now "active" or "unhealthy". Raise an error if unhealthy.
    if instance_status == "unhealthy":
        raise ValueError("Instance is unhealthy.")

    total_time = time.time() - start_time
    print(f"Instance booted in {total_time:.2f} seconds.")


def main():
    """Launch a Lambda Labs cloud instance from environment settings."""
    instance_params, lambda_token = get_and_validate_env_vars()
    response = launch_instance(instance_params, lambda_token)
    instance_id = handle_response(response)
    if instance_id:
        wait_for_boot(instance_id, lambda_token)


if __name__ == "__main__":
    main()
