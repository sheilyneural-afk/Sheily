path "transit/verify/governance-capability" {
  capabilities = ["update"]
}
path "transit/sign/*" {
  capabilities = ["deny"]
}
path "secret/data/*" {
  capabilities = ["deny"]
}
