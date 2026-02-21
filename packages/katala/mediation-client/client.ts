import * as grpc from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import axios from "axios";
import * as path from "path";

export interface ClientOptions {
  target: string; // e.g. "100.77.205.126:18789" or "http://..."
  token?: string;
  protocol: "grpc" | "http";
}

export class KatalaMediationClient {
  private options: ClientOptions;
  private grpcClient: any = null;

  constructor(options: ClientOptions) {
    this.options = options;
    if (options.protocol === "grpc") {
      const protoPath = path.resolve(__dirname, "../proto/synergy.proto");
      const packageDefinition = protoLoader.loadSync(protoPath, {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true,
      });
      const synergyProto = grpc.loadPackageDefinition(packageDefinition) as any;
      const target = options.target.includes("://")
        ? options.target.split("://")[1]
        : options.target;
      this.grpcClient = new synergyProto.synergy.Mediation(
        target,
        grpc.credentials.createInsecure(),
      );
    }
  }

  async handshake(clientId: string, version: string = "Katala-Sirokuma-v1") {
    if (this.options.protocol === "grpc") {
      return this.handshakeGrpc(clientId, version);
    } else {
      return this.handshakeHttp(clientId, version);
    }
  }

  private handshakeGrpc(clientId: string, version: string): Promise<any> {
    return new Promise((resolve, reject) => {
      const metadata = new grpc.Metadata();
      if (this.options.token) {
        metadata.add("Authorization", `Bearer ${this.options.token}`);
      }

      this.grpcClient.handshake(
        { client_id: clientId, version: version },
        metadata,
        (err: any, response: any) => {
          if (err) reject(err);
          else resolve(response);
        },
      );
    });
  }

  private async handshakeHttp(clientId: string, version: string) {
    const url = this.options.target.startsWith("http")
      ? this.options.target
      : `http://${this.options.target}`;

    // Try /api/v1/chat/completions or /hooks as per requirements
    const endpoint = `${url}/api/v1/chat/completions`;

    const headers: any = {
      "User-Agent": "Katala-Sirokuma-v1",
    };

    if (this.options.token) {
      headers["Authorization"] = `Bearer ${this.options.token}`;
    }

    try {
      const response = await axios.post(
        endpoint,
        {
          client_id: clientId,
          version: version,
        },
        { headers },
      );
      return response.data;
    } catch (error: any) {
      throw new Error(`HTTP Request failed: ${error.message}`);
    }
  }
}
