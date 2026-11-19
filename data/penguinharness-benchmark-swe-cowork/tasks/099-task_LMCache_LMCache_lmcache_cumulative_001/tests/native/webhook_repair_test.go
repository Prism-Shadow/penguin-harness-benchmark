package webhook

import (
    "context"
    "encoding/json"
    "reflect"
    "strings"
    "testing"

    jsonpatch "github.com/evanphx/json-patch/v5"
    engineapi "github.com/LMCache/LMCache/api/v1alpha1"
    "github.com/LMCache/LMCache/internal/resources"
    admissionv1 "k8s.io/api/admission/v1"
    corev1 "k8s.io/api/core/v1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/client/fake"
    "sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

func repairEngine(namespace, image string) *engineapi.CacheBlendEngine {
    tag := "v7"
    engine := &engineapi.CacheBlendEngine{
        ObjectMeta: metav1.ObjectMeta{Name: "shared-name", Namespace: namespace},
        Spec: engineapi.CacheBlendEngineSpec{
            L1: engineapi.L1BackendSpec{SizeGB: 2},
            Injection: &engineapi.InjectionSpec{PayloadImage: &engineapi.ImageSpec{Repository: &image, Tag: &tag}},
        },
    }
    engine.SetDefaults()
    return engine
}

func repairPod(reference string) corev1.Pod {
    return corev1.Pod{
        TypeMeta: metav1.TypeMeta{APIVersion: "v1", Kind: "Pod"},
        ObjectMeta: metav1.ObjectMeta{Name: "workload", Namespace: "tenant-a", Annotations: map[string]string{"lmcache.ai/cacheblend-engine": reference}},
        Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "vllm", Image: "workload:v2", Args: []string{"serve", "model-a"}, Env: []corev1.EnvVar{{Name: "KEEP", Value: "original"}}}}},
    }
}

func repairInject(test *testing.T, pod corev1.Pod, objects ...client.Object) corev1.Pod {
    test.Helper()
    scheme := runtime.NewScheme()
    if err := corev1.AddToScheme(scheme); err != nil { test.Fatal(err) }
    if err := engineapi.AddToScheme(scheme); err != nil { test.Fatal(err) }
    injector := CacheBlendPodInjector{Client: fake.NewClientBuilder().WithScheme(scheme).WithObjects(objects...).Build(), Decoder: admission.NewDecoder(scheme)}
    original, err := json.Marshal(pod)
    if err != nil { test.Fatal(err) }
    response := injector.Handle(context.Background(), admission.Request{AdmissionRequest: admissionv1.AdmissionRequest{Operation: admissionv1.Create, Namespace: pod.Namespace, Object: runtime.RawExtension{Raw: original}}})
    if !response.Allowed { test.Fatalf("admission rejected: %+v", response.Result) }
    if len(response.Patches) == 0 { return pod }
    encoded, err := json.Marshal(response.Patches)
    if err != nil { test.Fatal(err) }
    patch, err := jsonpatch.DecodePatch(encoded)
    if err != nil { test.Fatal(err) }
    updated, err := patch.Apply(original)
    if err != nil { test.Fatal(err) }
    var result corev1.Pod
    if err := json.Unmarshal(updated, &result); err != nil { test.Fatal(err) }
    return result
}

func TestCacheBlendAdmission(test *testing.T) {
    engine := repairEngine("tenant-a", "payload/local")
    objects := []client.Object{engine, resources.BuildCBConnectionConfigMap(engine)}
    original := repairPod("shared-name")
    updated := repairInject(test, original, objects...)
    if len(updated.Spec.InitContainers) != 1 || !updated.Spec.HostIPC { test.Fatalf("not injected: %+v", updated.Spec) }
    preserved := false
    for _, variable := range updated.Spec.Containers[0].Env { if variable == original.Spec.Containers[0].Env[0] { preserved = true } }
    if !preserved { test.Fatal("lost unrelated environment") }
    repeated := repairInject(test, updated, objects...)
    if !reflect.DeepEqual(updated.Spec, repeated.Spec) { test.Fatal("injection is not idempotent") }
    original.Annotations = nil
    unchanged := repairInject(test, original, objects...)
    if !reflect.DeepEqual(original.Spec, unchanged.Spec) { test.Fatal("mutated non-opted-in pod") }
}

func TestNamespaceIsolation(test *testing.T) {
    local := repairEngine("tenant-a", "payload/local")
    remote := repairEngine("tenant-b", "payload/remote")
    objects := []client.Object{local, remote, resources.BuildCBConnectionConfigMap(local), resources.BuildCBConnectionConfigMap(remote)}
    for reference, expected := range map[string]string{"shared-name": "payload/local:v7", "tenant-b/shared-name": "payload/remote:v7"} {
        result := repairInject(test, repairPod(reference), objects...)
        if len(result.Spec.InitContainers) != 1 || result.Spec.InitContainers[0].Image != expected { test.Fatalf("wrong tenant for %s: %+v", reference, result.Spec.InitContainers) }
        if reference == "tenant-b/shared-name" && !strings.Contains(strings.Join(result.Spec.Containers[0].Args, " "), "tenant-b") { test.Fatal("connection config came from wrong namespace") }
    }
    missing := repairInject(test, repairPod("missing/shared-name"), objects...)
    if len(missing.Spec.InitContainers) != 0 || len(missing.Annotations) <= 1 { test.Fatal("missing tenant must skip with reason") }
}
