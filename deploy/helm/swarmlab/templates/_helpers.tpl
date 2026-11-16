{{- define "swarmlab.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "swarmlab.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "swarmlab.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "swarmlab.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "swarmlab.selectorLabels" -}}
app.kubernetes.io/name: {{ include "swarmlab.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "swarmlab.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "swarmlab.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "swarmlab.databaseEnv" -}}
{{- if .Values.postgresql.enabled -}}
- name: SWARMLAB_DB
  valueFrom:
    secretKeyRef:
      name: {{ required "postgresql.existingSecret is required when postgresql.enabled" .Values.postgresql.existingSecret }}
      key: {{ .Values.postgresql.dsnKey }}
{{- else -}}
- name: SWARMLAB_DB
  value: /data/swarm.db
{{- end -}}
{{- end -}}

{{- define "swarmlab.authEnv" -}}
{{- if .Values.auth.enabled }}
- name: SWARMLAB_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ default (printf "%s-secrets" (include "swarmlab.fullname" .)) .Values.auth.existingSecret }}
      key: {{ .Values.auth.tokenKey }}
{{- if .Values.auth.tokens }}
- name: SWARMLAB_TOKENS
  value: {{ .Values.auth.tokens | quote }}
{{- end }}
{{- end }}
{{- end -}}
