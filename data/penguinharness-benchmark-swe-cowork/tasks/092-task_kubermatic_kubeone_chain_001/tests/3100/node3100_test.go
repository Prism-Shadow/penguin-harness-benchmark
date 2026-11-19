package tasks

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/sirupsen/logrus"
	kubeoneapi "k8c.io/kubeone/pkg/apis/kubeone"
	"k8c.io/kubeone/pkg/executor"
	"k8c.io/kubeone/pkg/state"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

type benchmarkPermissionRemote struct {
	root string
	fail string
	calls int
	failureInjected bool
}

func (remote *benchmarkPermissionRemote) Open(host kubeoneapi.HostConfig) (executor.Interface, error) {
	if host.Hostname != "cp" { return nil, fmt.Errorf("unexpected chmod on worker %q", host.Hostname) }
	if remote.fail == "open" { remote.failureInjected = true; return nil, fmt.Errorf("open denied") }
	return remote, nil
}
func (*benchmarkPermissionRemote) Tunnel(kubeoneapi.HostConfig) (executor.Tunneler, error) { return nil, fmt.Errorf("unexpected tunnel") }
func (*benchmarkPermissionRemote) Close() error { return nil }
func (remote *benchmarkPermissionRemote) Exec(command string) (string, string, int, error) {
	var stdout, stderr bytes.Buffer
	code, err := remote.POpen(command, nil, &stdout, &stderr)
	return stdout.String(), stderr.String(), code, err
}
func (remote *benchmarkPermissionRemote) POpen(command string, stdin io.Reader, stdout, stderr io.Writer) (int, error) {
	remote.calls++
 if remote.fail == "glob" && remote.calls == 1 {remote.failureInjected=true;return 1,fmt.Errorf("glob denied")}
 if remote.fail == "chmod-exit" && strings.Contains(command,"chmod") {remote.failureInjected=true;return 1,nil}
	if remote.fail != "" && strings.Contains(command, remote.fail) { remote.failureInjected = true; return 1, fmt.Errorf("%s denied", remote.fail) }
	command = strings.TrimPrefix(command, "sudo ")
	command = strings.NewReplacer(
		"/lib/", remote.root + "/lib/",
		"/etc/", remote.root + "/etc/",
		"/var/", remote.root + "/var/",
	).Replace(command)
	process := exec.Command("bash", "-c", command)
	var output bytes.Buffer
	process.Stdin, process.Stdout, process.Stderr = stdin, &output, stderr
	err := process.Run()
	if stdout != nil { _, _ = io.WriteString(stdout, strings.ReplaceAll(output.String(), remote.root, "")) }
	if process.ProcessState == nil { return 1, err }
	return process.ProcessState.ExitCode(), err
}

type benchmarkPermissionClient struct {
	client.Client
	fail bool
	lists int
	transition bool
}
func (kube *benchmarkPermissionClient) List(ctx context.Context, list client.ObjectList, options ...client.ListOption) error {
	kube.lists++
	if kube.fail { return fmt.Errorf("list denied") }
	if err := kube.Client.List(ctx, list, options...); err != nil { return err }
	if kube.transition && kube.lists > 1 {
		nodes := list.(*corev1.NodeList)
		for index := range nodes.Items { nodes.Items[index].Status.Conditions = []corev1.NodeCondition{{Type: corev1.NodeReady, Status: corev1.ConditionTrue}} }
	}
	return nil
}

func TestBenchmarkFilePermissionTaskIsInResourceLifecycle(t *testing.T) {
	t.Run("remote-path-mapping", func(t *testing.T) {
		root := filepath.Join(t.TempDir(), "var", "lib", "remote root")
		remote := &benchmarkPermissionRemote{root: root}
		for _, name := range []string{"/lib/systemd/fixture", "/etc/cni/fixture", "/var/lib/kubelet/fixture"} {
			path := filepath.Join(root, name)
			if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil { t.Fatal(err) }
			if err := os.WriteFile(path, []byte("config"), 0644); err != nil { t.Fatal(err) }
			stdout, stderr, code, err := remote.Exec(fmt.Sprintf("sudo stat -c %%s %q", name))
			if err != nil || code != 0 || strings.TrimSpace(stdout) != "6" {
				t.Fatalf("stat %s: output=%q stderr=%q code=%d error=%v", name, stdout, stderr, code, err)
			}
			_, stderr, code, err = remote.Exec(fmt.Sprintf("sudo chmod 0600 %q", name))
			if err != nil || code != 0 { t.Fatalf("chmod %s: stderr=%q code=%d error=%v", name, stderr, code, err) }
			info, err := os.Stat(path)
			if err != nil { t.Fatal(err) }
			if info.Mode().Perm() != 0600 { t.Fatalf("%s: mode %o", name, info.Mode().Perm()) }
		}
	})
	var repair func(*state.State) error
	for _, task := range WithResources(nil) {
		if task.Operation == "Fix permissions of system files" { repair = task.Fn }
	}
	if repair == nil { t.Fatal("resource lifecycle does not schedule permission repair") }
	for _, scenario := range []string{"ready", "empty-cluster", "missing-ready", "false-ready", "unknown-ready", "transition", "list", "open", "glob", "stat", "chmod", "chmod-exit"} {
		t.Run(scenario, func(t *testing.T) {
			root := t.TempDir()
			files := []string{"lib/systemd/system/kubelet.service", "lib/systemd/system/kubelet.service.d/10.conf", "etc/systemd/system/kubelet.service", "etc/systemd/system/kubelet.service.d/20.conf", "var/lib/kubelet/config.yaml", "etc/cni/net.d/10-network.conflist", "etc/cni/net.d/space name.conflist", "etc/cni/net.d/quoted '$dollar; config", "etc/cni/net.d/line\nname", "etc/cni/net.d/ trailing space ", "etc/cni/net.d/.hidden", "etc/untouched"}
			for _, name := range files {
				path := filepath.Join(root, name)
				if err := os.MkdirAll(filepath.Dir(path), 0777); err != nil { t.Fatal(err) }
				if err := os.WriteFile(path, []byte("config"), 0644); err != nil { t.Fatal(err) }
			}
			directories := []string{"lib/systemd/system/kubelet.service.d", "etc/systemd/system/kubelet.service.d"}
			for _, name := range directories { if err := os.Chmod(filepath.Join(root, name), 0755|os.ModeSetgid|os.ModeSticky); err != nil { t.Fatal(err) } }
			if err := os.Chmod(filepath.Join(root, files[0]), 0600|os.ModeSetuid|os.ModeSetgid); err != nil {t.Fatal(err)}
            scheme := runtime.NewScheme()
			if err := corev1.AddToScheme(scheme); err != nil { t.Fatal(err) }
			conditions := []corev1.NodeCondition{{Type: corev1.NodeReady, Status: corev1.ConditionTrue}}
			switch scenario {
			case "missing-ready": conditions = nil
			case "false-ready", "transition": conditions[0].Status = corev1.ConditionFalse
			case "unknown-ready": conditions[0].Status = corev1.ConditionUnknown
			}
			node := &corev1.Node{ObjectMeta: metav1.ObjectMeta{Name: "cp"}, Status: corev1.NodeStatus{Conditions: conditions}}
			objects:=[]client.Object{node};if scenario=="empty-cluster"{objects=nil}
            kube := &benchmarkPermissionClient{Client: fake.NewClientBuilder().WithScheme(scheme).WithObjects(objects...).Build(), fail: scenario == "list", transition: scenario == "transition"}
			remote := &benchmarkPermissionRemote{root: root}
			if scenario == "open" || scenario == "glob" || scenario == "stat" || scenario == "chmod" || scenario == "chmod-exit" { remote.fail = scenario }
			duration := 100 * time.Millisecond
			if scenario == "ready" || scenario == "transition" { duration = 12 * time.Second }
			ctx, cancel := context.WithTimeout(context.Background(), duration)
			defer cancel()
			current := &state.State{Context: ctx, Logger: logrus.New(), DynamicClient: kube, Executor: remote, Cluster: &kubeoneapi.KubeOneCluster{
				ControlPlane: kubeoneapi.ControlPlaneConfig{Hosts: []kubeoneapi.HostConfig{{Hostname: "cp"}}},
				StaticWorkers: kubeoneapi.StaticWorkersConfig{Hosts: []kubeoneapi.HostConfig{{Hostname: "worker"}}},
			}}
			err := repair(current)
			if scenario != "ready" && scenario != "transition" {
				if err == nil { t.Fatal("failed operation or unready node must return an error") }
				if remote.fail != "" && !remote.failureInjected { t.Fatalf("did not reach injected %s failure: %v", remote.fail, err) }
				if (strings.Contains(scenario, "ready") || scenario=="empty-cluster") && remote.calls != 0 { t.Fatal("remote operations ran before NodeReady") }
				return
			}
			if err != nil { t.Fatal(err) }
			if scenario == "transition" && kube.lists < 2 { t.Fatal("did not wait for Ready transition") }
			for _, name := range append(files, directories...) {
				info, err := os.Stat(filepath.Join(root, name))
				if err != nil { t.Fatal(err) }
				want := os.FileMode(0600)
				if info.IsDir() { want = 0755 }
				if name == "etc/untouched" { want = 0644 }
				if info.Mode()&(os.ModePerm|os.ModeSetuid|os.ModeSetgid|os.ModeSticky) != want { t.Errorf("%s: mode %o, want %o", name, info.Mode().Perm(), want) }
			}
		})
	}
}
