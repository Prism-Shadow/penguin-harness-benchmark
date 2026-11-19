package contract

import (
	"testing"
 "strings"

	"k8c.io/kubeone/pkg/templates/images"
)

func TestBenchmarkCalicoImageRevision(t *testing.T) {
	resolver := images.NewResolver(images.WithKubernetesVersionGetter(func() string { return "1.29.2" }))
	for _,ref:=range resolver.List(images.ListFilterNone){
  if strings.HasPrefix(ref,"quay.io/calico/")&&!strings.HasSuffix(ref,":v3.27.2"){t.Fatalf("public image catalog retains an obsolete Calico alias: %s",ref)}
 }
 got := resolver.Get(images.CalicoCNI)
	if got != "quay.io/calico/cni:v3.27.2" {
		t.Fatalf("Calico CNI image = %q, want v3.27.2", got)
	}
}
