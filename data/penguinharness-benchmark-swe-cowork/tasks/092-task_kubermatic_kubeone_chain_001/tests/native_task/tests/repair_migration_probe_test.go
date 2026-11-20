package tasks
import (
 "context"
 "testing"
 api "k8c.io/kubeone/pkg/apis/kubeone"
 "k8c.io/kubeone/pkg/state"
 core "k8s.io/api/core/v1"
 meta "k8s.io/apimachinery/pkg/apis/meta/v1"
 "k8s.io/apimachinery/pkg/runtime"
 "sigs.k8s.io/controller-runtime/pkg/client/fake"
)
func TestRepairMigrationStateDetection(t *testing.T) {
 for _,p:=range []api.CloudProviderSpec{{AWS:&api.AWSSpec{}},{Azure:&api.AzureSpec{}},{GCE:&api.GCESpec{}},{Openstack:&api.OpenstackSpec{}},{Vsphere:&api.VsphereSpec{}}}{for _,completed:=range []bool{false,true}{
  scheme:=runtime.NewScheme();if err:=core.AddToScheme(scheme);err!=nil{t.Fatal(err)}
  flag:="--feature-gates=DisableCloudProviders=false";if completed{flag="--feature-gates=DisableCloudProviders=true"}
  pod:=&core.Pod{ObjectMeta:meta.ObjectMeta{Name:"controller",Namespace:meta.NamespaceSystem,Labels:map[string]string{"component":"kube-controller-manager"}},Spec:core.PodSpec{Containers:[]core.Container{{Name:"controller",Command:[]string{"controller","--cloud-provider=external",flag}}}}}
  s:=&state.State{Context:context.Background(),Cluster:&api.KubeOneCluster{CloudProvider:p},DynamicClient:fake.NewClientBuilder().WithScheme(scheme).WithObjects(pod).Build()}
  status,err:=detectCCMMigrationStatus(s);if err!=nil{t.Fatal(err)}
  if !status.CSIMigrationEnabled || status.InTreeCloudProviderUnregistered!=completed || status.InTreeCloudProviderEnabled || status.ExternalCCMDeployed {t.Fatalf("incorrect observed migration state: %#v",status)}
 }}
}
