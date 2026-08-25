path "transit/sign/audit-receipt" {
  capabilities = ["update"]
}
path "transit/verify/*" {
  capabilities = ["update"]
}
path "secret/data/*" {
  capabilities = ["deny"]
}
