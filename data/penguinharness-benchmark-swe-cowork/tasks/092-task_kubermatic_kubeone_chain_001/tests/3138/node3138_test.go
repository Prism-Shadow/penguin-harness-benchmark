package executorfs

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
 "io/fs"
)

type benchmarkStatExecutor struct {
	broken bool
	failed bool
 record string
 exitOnly bool
}

func (remote benchmarkStatExecutor) Exec(command string) (string, string, int, error) {
	var stdout, stderr bytes.Buffer
	code, err := remote.POpen(command, nil, &stdout, &stderr)
	return stdout.String(), stderr.String(), code, err
}

func (remote benchmarkStatExecutor) POpen(command string, stdin io.Reader, stdout, stderr io.Writer) (int, error) {
	if remote.failed { return 1, fmt.Errorf("remote stat denied") }
    if remote.exitOnly {return 1,nil}
    if remote.record!="" {_,err:=io.WriteString(stdout,remote.record);return 0,err}
	if remote.broken {
		_, err := io.WriteString(stdout, "invalid-stat-record")
		return 0, err
	}
	process := exec.Command("bash", "-c", strings.TrimPrefix(command, "sudo "))
	process.Stdin, process.Stdout, process.Stderr = stdin, stdout, stderr
	err := process.Run()
	if process.ProcessState == nil { return 1, err }
	return process.ProcessState.ExitCode(), err
}

func (benchmarkStatExecutor) Close() error { return nil }

func TestBenchmarkSSHStatPreservesDirectoryMode(t *testing.T) {
	directory := t.TempDir()
	file := filepath.Join(directory, "regular file")
	if err := os.WriteFile(file, []byte("payload"), 0640); err != nil { t.Fatal(err) }
	if err := os.Chmod(directory, 0755); err != nil { t.Fatal(err) }
	modified := time.Unix(1700000000, 0)
	for _, name := range []string{directory, file} {
		if err := os.Chtimes(name, modified, modified); err != nil { t.Fatal(err) }
		wanted, err := os.Stat(name)
		if err != nil { t.Fatal(err) }
		actual, err := newSSHFileInfo(name, benchmarkStatExecutor{})
		if err != nil { t.Fatalf("stat %q: %v", name, err) }
		if actual.IsDir() != wanted.IsDir() || actual.Mode().Perm() != wanted.Mode().Perm() || actual.Size() != wanted.Size() || !actual.ModTime().Equal(modified) {
			t.Fatalf("stat mismatch: got %v, want %v", actual, wanted)
		}
	}
	for _,remote:=range []benchmarkStatExecutor{{broken:true},{failed:true},{exitOnly:true},
        {record:"12garbage\t81a0\t1700000000\tregular file"},
        {record:"-1\t81a0\t1700000000\tregular file"},
        {record:"12\t81a0junk\t1700000000\tregular file"},
        {record:"12\t81a0\t1700000000junk\tregular file"},
        {record:"12\t81a0\t1700000000\tinvalid-type"}} {
		if _, err := newSSHFileInfo(file, remote); err == nil { t.Fatal("invalid or failed stat must return an error") }
	}
}

func TestRepairStatSpecialNamesAndModes(t *testing.T) {
 directory:=t.TempDir()
 for _,name:=range []string{"regular 'quoted' $dollar ; name","regular\nnewline"}{
  path:=filepath.Join(directory,name)
  if err:=os.WriteFile(path,[]byte("special file content"),0600);err!=nil{t.Fatal(err)}
  if err:=os.Chmod(path,0640|os.ModeSetuid|os.ModeSetgid);err!=nil{t.Fatal(err)}
  actual,err:=newSSHFileInfo(path,benchmarkStatExecutor{});if err!=nil{t.Fatal(err)}
  wanted,err:=os.Lstat(path);if err!=nil{t.Fatal(err)}
  if actual.Size()!=wanted.Size()||actual.Mode()!=wanted.Mode(){t.Fatalf("special mode mismatch: %v != %v",actual.Mode(),wanted.Mode())}
 }
 link:=filepath.Join(directory,"symbolic link");if err:=os.Symlink(directory,link);err!=nil{t.Fatal(err)}
 actual,err:=newSSHFileInfo(link,benchmarkStatExecutor{});if err!=nil{t.Fatal(err)}
 if actual.Mode()&os.ModeSymlink==0||actual.IsDir(){t.Fatal("symbolic link type was lost")}
}

func TestRepairChmodRefreshesStat(t *testing.T) {
 path:=filepath.Join(t.TempDir(),"mode 'quoted' $name")
 if err:=os.WriteFile(path,[]byte("payload"),0644);err!=nil{t.Fatal(err)}
 file,err:=New(benchmarkStatExecutor{}).Open(path);if err!=nil{t.Fatal(err)}
 before,err:=file.Stat();if err!=nil||before.Mode().Perm()!=0644{t.Fatalf("initial stat: %v %v",before,err)}
 chmod,ok:=file.(interface{Chmod(fs.FileMode) error});if !ok{t.Fatal("remote file lacks chmod")}
 if err:=chmod.Chmod(0600);err!=nil{t.Fatal(err)}
 after,err:=file.Stat();if err!=nil||after.Mode().Perm()!=0600{t.Fatalf("cached stat did not reflect chmod: %v %v",after,err)}
}
