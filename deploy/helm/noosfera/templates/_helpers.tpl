{{- define "noosfera.labels" -}}
app.kubernetes.io/part-of: noosfera
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}
