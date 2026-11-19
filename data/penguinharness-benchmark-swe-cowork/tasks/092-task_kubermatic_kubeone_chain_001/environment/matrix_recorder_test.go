//go:build e2e

package e2e

import (
 "context"
 "encoding/json"
 "flag"
 "fmt"
 "io"
 "os"
 "reflect"
 "sync"
 "testing"
)

// Record the submitted suite at its cloud-execution boundary. Submitted test
// functions, package initialization, and all argument setters still execute.
type matrixRecorder struct {
 original Scenario
 scenario string
 infra Infra
 infraSet bool
 versions []string
 initial string
}
var matrixMutex sync.Mutex
func (r *matrixRecorder) SetInfra(infra Infra) { r.infra = infra; r.infraSet=true }
func (r *matrixRecorder) SetVersions(versions ...string) { r.versions = append([]string(nil), versions...) }
func (r *matrixRecorder) SetInitKubeOneVersion(initial string) { r.initial = initial }
func (r *matrixRecorder) GenerateTests(w io.Writer, kind GeneratorType, cfg ProwConfig) error {
 return r.original.GenerateTests(w, kind, cfg)
}
func (r *matrixRecorder) Run(_ context.Context, t *testing.T) {
 t.Helper()
 if !r.infraSet || len(r.versions) == 0 { t.Fatal("scenario did not receive infrastructure and versions") }
 // Resolve the argument against the production registry without naming any
 // private Infra field. A refactor of its representation remains valid.
 infrastructure := ""
 for name, candidate := range Infrastructures {
  if reflect.DeepEqual(r.infra,candidate) {
   if infrastructure!="" {t.Fatal("ambiguous infrastructure registry value")}
   infrastructure=name
  }
 }
 if infrastructure=="" {t.Fatal("scenario infrastructure was not registered")}
 row := map[string]interface{}{
  "test": t.Name(), "infra": infrastructure, "provider": r.infra.Provider(),
  "scenario": r.scenario, "versions": r.versions, "initial": r.initial,
  "verbose": testing.Verbose(), "selector": flag.Lookup("test.run").Value.String(),
  "timeout": flag.Lookup("test.timeout").Value.String(),
 }
 matrixMutex.Lock()
 defer matrixMutex.Unlock()
 f, err := os.OpenFile(os.Getenv("MATRIX_RECORDS"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
 if err != nil { t.Fatal(err) }
 defer f.Close()
 if err := json.NewEncoder(f).Encode(row); err != nil { t.Fatal(err) }
}
func init() {
 if os.Getenv("MATRIX_RECORDS") == "" { fmt.Fprintln(os.Stderr, "MATRIX_RECORDS is required"); os.Exit(2) }
 for name, implementation := range Scenarios {
  Scenarios[name] = &matrixRecorder{original: implementation, scenario: name}
 }
}
