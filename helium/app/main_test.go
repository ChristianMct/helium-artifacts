package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"testing"

	"github.com/ChristianMct/helium"
	"github.com/ChristianMct/helium/circuits"
	"github.com/ChristianMct/helium/node"
	"github.com/ChristianMct/helium/services/compute"
	"github.com/ChristianMct/helium/sessions"
	"github.com/stretchr/testify/require"
	"github.com/tuneinsight/lattigo/v5/schemes/bgv"
	"golang.org/x/sync/errgroup"
	"google.golang.org/grpc/test/bufconn"
)

const buffConBufferSize = 65 * 1024 * 1024

func TestApp(t *testing.T) {

	nParty := 4
	threshold := 3
	nRep := 10

	nids, nl, shamirPks, nodeMapping := genNodeLists(nParty, "local")

	hid := sessions.NodeID("cloud")

	hconf := genConfigForNode(hid, nids, threshold, shamirPks)
	cloudn, err := node.New(hconf, nl)
	require.NoError(t, err)
	cloud := helium.NewHeliumServer(cloudn)

	//clins := make([]*node.Node, 0, len(nids))
	clis := make([]*helium.HeliumClient, 0, len(nids))
	for _, nid := range nids {
		clin, err := node.New(genConfigForNode(nid, nids, threshold, shamirPks), nl)
		require.NoError(t, err)
		//clins = append(clins, clin)
		clis = append(clis, helium.NewHeliumClient(clin, hid, "local"))
	}

	lis := bufconn.Listen(buffConBufferSize)
	go cloud.Serve(lis)

	params, err := bgv.NewParametersFromLiteral(hconf.SessionParameters[0].FHEParameters.(bgv.ParametersLiteral))
	if err != nil {
		panic(err)
	}

	m := params.MaxSlots() / 2
	app := getApp(params, m)
	a := genTestMatrix(m)
	encoder := bgv.NewEncoder(params) // TODO pass encoder in ip ?

	ctx := sessions.NewBackgroundContext("test-session")
	g, runctx := errgroup.WithContext(ctx)
	g.Go(func() error {
		cdescs, outs, err := cloud.Run(runctx, app, compute.NoInput)
		if err != nil {
			return err
		}

		if err := encryptTestMatrix(ctx, a, params, cloud, cloud); err != nil {
			log.Fatalf("error encrypting test matrix: %v", err)
		}

		go func() {
			for i := 0; i < nRep; i++ {
				cdescs <- circuits.Descriptor{
					Signature:   circuits.Signature{Name: "matmul4-dec"},
					CircuitID:   sessions.CircuitID(fmt.Sprintf("matmul-%d", i)),
					NodeMapping: nodeMapping,
					Evaluator:   "cloud",
				}
			}
			close(cdescs)
		}()

		for out := range outs {
			return fmt.Errorf("should not have output, got %s", out.OperandLabel)
		}

		cloud.GracefulStop()

		return nil
	})

	for _, cli := range clis {
		cli := cli

		g.Go(func() error {
			err = cli.ConnectWithDialer(func(c context.Context, addr string) (net.Conn, error) { return lis.Dial() })
			if err != nil {
				return fmt.Errorf("node %s failed to connect: %v", cli, err)
			}

			ip := compute.NoInput
			if cli.NodeID() == "node-0" {
				encoder := bgv.NewEncoder(params)
				ip = getInputProvider(params, encoder, m)
			}

			outs, err := cli.Run(runctx, app, ip)
			if err != nil {
				return err
			}

			for out := range outs {
				if cli.NodeID() == "node-0" {
					if err = checkResultCorrect(params, *encoder, out, a); err != nil {
						return fmt.Errorf("incorrect result for: output %s: %v", out.OperandLabel, err)
					}

				} else {
					return fmt.Errorf("should not have output, got %s", out.OperandLabel)
				}
			}

			cli.Close()
			return nil
		})
	}

	err = g.Wait()
	require.NoError(t, err)

}
