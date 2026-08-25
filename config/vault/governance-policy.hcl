path "transit/sign/governance-capability" {
  capabilities = ["update"]
}
path "transit/verify/governance-capability" {
  capabilities = ["update"]
}
path "secret/data/*" {
  capabilities = ["deny"]
}
