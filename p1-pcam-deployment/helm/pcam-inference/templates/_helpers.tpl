{{/*
_helpers.tpl — reusable template fragments for the pcam-inference chart.

Helm partials are defined with `define` and called with `include` (not
`template`) because `include` can be piped to `indent`, `nindent`, etc.
`template` cannot — it always outputs to the root scope.

All helpers are prefixed with the chart name ("pcam-inference.") to avoid
collisions if this chart is used as a dependency inside a larger umbrella chart.
*/}}

{{/*
pcam-inference.fullname
----------------------
Produces the release-scoped name used for all K8s object names.
Standard Helm convention: "<release-name>-<chart-name>", truncated to
63 characters (DNS label limit). The `trunc 63 | trimSuffix "-"` idiom
is idiomatic Helm — it prevents names ending with a hyphen after truncation.

If the release name already contains the chart name (e.g. the user ran
`helm install pcam-inference ./helm/pcam-inference`), we skip the redundant
suffix to avoid "pcam-inference-pcam-inference".
*/}}
{{- define "pcam-inference.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
pcam-inference.labels
---------------------
Standard set of labels applied to every object in this chart.
app.kubernetes.io/* labels are the recommended Kubernetes common labels.
They enable `kubectl` selectors, Helm release tracking, and tooling like
Lens to group resources by app and version.
*/}}
{{- define "pcam-inference.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
pcam-inference.selectorLabels
------------------------------
Subset of labels used in Service and Deployment selectors.
Must be STABLE — changing selector labels after first deploy requires
deleting and recreating the Deployment (selectors are immutable).
We keep only name + instance here; version is intentionally excluded
so rolling updates don't break selector matching mid-rollout.
*/}}
{{- define "pcam-inference.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
