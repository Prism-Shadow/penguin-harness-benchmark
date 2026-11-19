package knowledge_compile

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"ragflow/internal/entity"
)

func TestRepairDurableSchedulerLifecycle(t *testing.T) {
	ctx := context.Background()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	sqlDB.SetMaxOpenConns(1)
	defer sqlDB.Close()
	s := newScheduler(db, nil, "first", time.Minute)
	if err = s.Provision(ctx); err != nil {
		t.Fatal(err)
	}
	if err = s.PublishVariants(ctx, "tenant", "kb", "doc", string(EventTypeCompleted), 0, []string{"wiki"}); err != nil {
		t.Fatal(err)
	}
	row, err := s.loadRow(ctx, "kb")
	if err != nil || row.State != entity.DatasetStatePending {
		t.Fatalf("pending row: %+v %v", row, err)
	}
	a, ok, err := s.Claim(ctx, "kb")
	if err != nil || !ok || a.Entries[0].Seq != 1 || len(a.Entries[0].Variants) != 1 {
		t.Fatalf("claim=%+v %v", a, err)
	}
	if err = s.Publish(ctx, "tenant", "kb", "doc", string(EventTypeCompleted), 0); err != nil {
		t.Fatal(err)
	}
	if err = s.UpdateProgress(ctx, "kb", a.Token, .4, "writing", "one"); err != nil {
		t.Fatal(err)
	}
	if err = s.SetError(ctx, "kb", "stale", "wrong"); err != nil {
		t.Fatal(err)
	}
	if n, err := s.Ack(ctx, "kb", a.Token, a.Entries); err != nil || n != 1 {
		t.Fatalf("ack %d %v", n, err)
	}
	row, _ = s.loadRow(ctx, "kb")
	if row.State != entity.DatasetStatePending {
		t.Fatalf("pending remaining: %+v", row)
	}
	// Restart a scheduler against the same storage: seq and dedup must survive.
	s = newScheduler(db, nil, "second", time.Minute)
	b, ok, err := s.Claim(ctx, "kb")
	if !ok || err != nil || b.Entries[0].Seq != 2 {
		t.Fatalf("second claim %+v %v", b, err)
	}
	if _, err = s.Ack(ctx, "kb", b.Token, b.Entries); err != nil {
		t.Fatal(err)
	}
	row, _ = s.loadRow(ctx, "kb")
	if row.State != entity.DatasetStateCompleted || row.Progress != 1 || row.LastCompletedAt == nil {
		t.Fatalf("completed row=%+v", row)
	}
	if err = s.Publish(ctx, "tenant", "kb", "doc", string(EventTypeDeleted), 1); err != nil {
		t.Fatal(err)
	}
	if _, ok, err = s.Claim(ctx, "kb"); err != nil || ok {
		t.Fatalf("stale deletion claimed: %v %v", ok, err)
	}
	if err = s.Publish(ctx, "tenant", "kb", "doc", string(EventTypeDeleted), 0); err != nil {
		t.Fatal(err)
	}
	c, ok, err := s.Claim(ctx, "kb")
	if !ok || err != nil || c.Entries[0].Seq != 3 {
		t.Fatalf("automatic seq after stale event %+v %v", c, err)
	}
	// Expired inflight and newly queued backlog must be reclaimed together.
	if err = s.Publish(ctx, "tenant", "kb", "other", string(EventTypeCompleted), 0); err != nil {
		t.Fatal(err)
	}
	if err = db.Model(&entity.KnowledgeCompileDataset{}).Where("dataset_id = ?", "kb").Update("claim_expires_at", time.Now().Add(-time.Minute)).Error; err != nil {
		t.Fatal(err)
	}
	d, ok, err := s.Claim(ctx, "kb")
	if !ok || err != nil || len(d.Entries) != 2 || d.Token == c.Token {
		t.Fatalf("reclaim lost work %+v %v", d, err)
	}
	if _, err = s.Ack(ctx, "kb", c.Token, c.Entries); !errors.Is(err, ErrClaimTokenMismatch) {
		t.Fatalf("stale ack=%v", err)
	}
	if _, err = s.Ack(ctx, "kb", d.Token, d.Entries); err != nil {
		t.Fatal(err)
	}
}

func TestRepairRebuildFencesStaleWritesEvenOnFailure(t *testing.T) {
	ctx := context.Background()
	s := NewFakeScheduler()
	if err := s.Publish(ctx, "t", "kb", "doc", string(EventTypeCompleted), 0); err != nil {
		t.Fatal(err)
	}
	claim, _, _ := s.Claim(ctx, "kb")
	consumer := NewConsumer(s, WithReader(&fakeReader{}), WithWriter(&fakeWriter{}))
	entered := make(chan struct{})
	release := make(chan struct{})
	rebuilt := make(chan error, 1)
	go func() {
		rebuilt <- s.ResetDataset(ctx, "t", "kb", func() ([]BacklogEntry, error) {
			close(entered)
			<-release
			return nil, errors.New("storage rejected clear")
		})
	}()
	<-entered
	wrote := false
	writeDone := make(chan error, 1)
	go func() {
		writeDone <- consumer.withWriteLock(ctx, "kb", claim.Token, func() error { wrote = true; return nil })
	}()
	select {
	case err := <-writeDone:
		t.Fatalf("write passed rebuild lock: %v", err)
	case <-time.After(20 * time.Millisecond):
	}
	close(release)
	if err := <-rebuilt; err == nil {
		t.Fatal("rebuild error swallowed")
	}
	if err := <-writeDone; !errors.Is(err, errClaimSuperseded) || wrote {
		t.Fatalf("stale writer=%v wrote=%v", err, wrote)
	}
	retry, ok, err := s.Claim(ctx, "kb")
	if !ok || err != nil || len(retry.Entries) != 1 {
		t.Fatalf("lost retry %+v %v", retry, err)
	}
}

func TestRepairConsumerPreservesVariantsAndRepeatedAutomaticEvents(t *testing.T) {
	ctx := context.Background()
	s := NewFakeScheduler()
	r := &fakeReader{products: sampleProducts()}
	w := &fakeWriter{}
	c := newTestConsumer(s, r, w, func(string) (Deduper, error) { return NewNoopDeduper(), nil })
	if err := s.PublishVariants(ctx, "t1", "kb1", "d1", string(EventTypeCompleted), 0, []string{"wiki"}); err != nil {
		t.Fatal(err)
	}
	c.tryClaimAndProcess(ctx)
	if len(w.written) != 0 {
		t.Fatal("Wiki-only event processed stale structure products")
	}
	for i := 0; i < 2; i++ {
		if err := s.PublishVariants(ctx, "t1", "kb1", "d1", string(EventTypeCompleted), 0, []string{"structure"}); err != nil {
			t.Fatal(err)
		}
		c.tryClaimAndProcess(ctx)
	}
	if len(w.written) != 2 {
		t.Fatalf("second automatic completion lost: writes=%d", len(w.written))
	}
	if err := s.Publish(ctx, "t1", "kb1", "d1", string(EventTypeDeleted), 1); err != nil {
		t.Fatal(err)
	}
	c.tryClaimAndProcess(ctx)
	if len(w.deletedDocLevel) != 0 {
		t.Fatal("stale delete removed reingested document")
	}
}
