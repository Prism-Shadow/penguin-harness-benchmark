package webhook

import (
    "reflect"
    "strings"
    "testing"

    corev1 "k8s.io/api/core/v1"
)

func TestPayloadStaging(test *testing.T) {
    for _, image := range []string{"registry/a:one", "registry/b:two"} {
        volume := BuildCBPluginVolume()
        init := BuildCBInitContainer(image, corev1.PullNever)
        mount := BuildCBVolumeMount()
        if volume.EmptyDir == nil || volume.HostPath != nil { test.Fatal("staging must be pod-local") }
        if init.Image != image || init.ImagePullPolicy != corev1.PullNever || len(init.VolumeMounts) != 1 { test.Fatalf("lost image or mounts: %+v", init) }
        if init.VolumeMounts[0].Name != volume.Name || mount.Name != volume.Name || mount.MountPath != init.VolumeMounts[0].MountPath { test.Fatal("staging paths disagree") }
        if init.VolumeMounts[0].ReadOnly || !mount.ReadOnly { test.Fatal("incorrect staging ownership") }
        existing := []corev1.EnvVar{{Name: "OTHER", Value: "kept"}, {Name: "PYTHONPATH", Value: "/existing"}}
        result := BuildCBPodEnv(existing)
        if existing[1].Value != "/existing" { test.Fatal("mutated input environment") }
        variables := map[string]string{}
        for _, variable := range result { variables[variable.Name] = variable.Value }
        if variables["OTHER"] != "kept" || variables["PYTHONPATH"] != mount.MountPath+":/existing" { test.Fatal("payload not prepended or unrelated variable lost") }
    }
}

func TestDynamicArguments(test *testing.T) {
    for _, existing := range [][]string{{"serve", "model", "--unrelated", "kept"}, {"serve", "other", "--pipeline-parallel-size=9"}} {
        snapshot := append([]string(nil), existing...)
        result := BuildCBArgs(existing, `{"test":"connection"}`, "eager")
        if !reflect.DeepEqual(existing, snapshot) { test.Fatal("builder mutated caller args") }
        if !reflect.DeepEqual(result, BuildCBArgs(result, `{"test":"connection"}`, "eager")) { test.Fatal("duplicate dynamic arguments") }
        if result[0] != existing[0] || result[1] != existing[1] { test.Fatal("lost workload arguments") }
        for flag, expected := range map[string]string{"--attention-backend": "CUSTOM", "--block-size": "64", "--pipeline-parallel-size": "1", "--kv-transfer-config": `{"test":"connection"}`} {
            value, count := "", 0
            for index, argument := range result {
                if argument == flag && index+1 < len(result) { value, count = result[index+1], count+1 }
                if strings.HasPrefix(argument, flag+"=") { value, count = strings.TrimPrefix(argument, flag+"="), count+1 }
            }
            if count != 1 || value != expected { test.Fatalf("%s must be set once to %s: %v", flag, expected, result) }
        }
        for _, flag := range []string{"--no-async-scheduling", "--no-enable-chunked-prefill", "--enforce-eager"} {
            count := 0
            for _, argument := range result { if argument == flag { count++ } }
            if count != 1 { test.Fatalf("%s missing or duplicated: %v", flag, result) }
        }
    }
}
