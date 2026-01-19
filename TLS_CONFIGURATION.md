# TLS Configuration Examples

This document shows how to configure TLS settings for the SUSE AI Observability Extension to work with self-signed certificates.

## Environment Variables

```bash
# Basic configuration with self-signed certificate verification
export STACKSTATE_TLS_SKIP_VERIFY=false
export STACKSTATE_TLS_CA_FILE="/path/to/ca.pem"

# Configuration with client certificate authentication
export STACKSTATE_TLS_SKIP_VERIFY=false
export STACKSTATE_TLS_CA_FILE="/path/to/ca.pem"
export STACKSTATE_TLS_CERT_FILE="/path/to/client.pem"
export STACKSTATE_TLS_KEY_FILE="/path/to/client-key.pem"

# Insecure configuration (not recommended for production)
export STACKSTATE_TLS_SKIP_VERIFY=true
```

## Configuration File

Add TLS settings to your configuration file:

```yaml
stackstate:
  api_url: "https://my-stackstate-server:8443"
  api_key: "your-api-key"
  api_token: "your-api-token"
  
  # TLS Configuration
  tls_skip_verify: false
  tls_ca_file: "/etc/ssl/certs/my-ca.pem"
  # Optional: for client certificate authentication
  tls_cert_file: "/etc/ssl/certs/client.pem"
  tls_key_file: "/etc/ssl/certs/client-key.pem"
```

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `tls_skip_verify` | Skip TLS certificate verification (insecure) | `true` |
| `tls_ca_file` | Path to CA certificate file for verification | `""` |
| `tls_cert_file` | Path to client certificate file | `""` |
| `tls_key_file` | Path to client private key file | `""` |

## Use Cases

### 1. Self-signed Certificate with Custom CA
```yaml
stackstate:
  tls_skip_verify: false
  tls_ca_file: "/path/to/ca.pem"
```

### 2. Client Certificate Authentication
```yaml
stackstate:
  tls_skip_verify: false
  tls_ca_file: "/path/to/ca.pem"
  tls_cert_file: "/path/to/client.pem"
  tls_key_file: "/path/to/client-key.pem"
```

### 3. Development/Testing (Insecure)
```yaml
stackstate:
  tls_skip_verify: true
```

## File Format Notes

- Certificate files should be in PEM format
- Both `tls_cert_file` and `tls_key_file` must be provided together if using client certificates
- File paths are relative to the application's working directory

## Backward Compatibility

The default behavior (`tls_skip_verify: true`) maintains backward compatibility with existing configurations.