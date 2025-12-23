#!/usr/bin/env python3
"""
Nebula Performance Benchmark Script

Measures upload, download, streaming, and transcoding performance for Nebula Cloud.

Usage:
    python benchmark.py /path/to/video.mp4 --server http://localhost:8000

Requirements:
    - Python 3.7+
    - requests
    - tqdm (for progress bars)
    - Install: pip install requests tqdm
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import requests
from tqdm import tqdm


class NebulaBenchmark:
    def __init__(self, server_url: str, verbose: bool = False):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.verbose = verbose
        self.uploaded_file_id = None

    def log(self, message: str):
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def measure_operation(self, operation_name: str, func, *args, **kwargs) -> Dict[str, Any]:
        """Measure execution time and throughput of an operation"""
        self.log(f"Starting {operation_name}...")
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time

            return {
                'operation': operation_name,
                'duration_seconds': duration,
                'success': True,
                'result': result
            }
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            return {
                'operation': operation_name,
                'duration_seconds': duration,
                'success': False,
                'error': str(e)
            }

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata"""
        path = Path(file_path)
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        return {
            'path': str(path),
            'filename': path.name,
            'size_bytes': size_bytes,
            'size_mb': size_mb
        }

    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload file and measure performance"""
        file_info = self.get_file_info(file_path)

        url = f"{self.server_url}/api/upload"
        self.log(f"Uploading {file_info['filename']} ({file_info['size_mb']:.1f} MB)...")

        with open(file_path, 'rb') as f:
            files = {'file': (file_info['filename'], f, 'application/octet-stream')}
            response = self.session.post(url, files=files)

        if response.status_code != 200:
            raise Exception(f"Upload failed: HTTP {response.status_code} - {response.text}")

        result = response.json()
        self.uploaded_file_id = result['file']['id']

        # Calculate throughput
        throughput_mbps = (file_info['size_mb'] * 8) / self.current_measurement['duration_seconds']

        return {
            'file_id': self.uploaded_file_id,
            'throughput_mbps': throughput_mbps,
            'response': result
        }

    def download_file(self, file_id: int) -> Dict[str, Any]:
        """Download file and measure performance"""
        url = f"{self.server_url}/api/files/{file_id}/download"

        # Get file info first to calculate expected size
        info_response = self.session.get(f"{self.server_url}/api/files/{file_id}")
        if info_response.status_code != 200:
            raise Exception(f"Could not get file info: HTTP {info_response.status_code}")

        file_info = info_response.json()
        expected_size = file_info['size']
        expected_mb = expected_size / (1024 * 1024)

        self.log(f"Downloading {expected_mb:.1f} MB...")

        response = self.session.get(url, stream=True)
        if response.status_code != 200:
            raise Exception(f"Download failed: HTTP {response.status_code}")

        # Download with progress
        downloaded = 0
        with tqdm(total=expected_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    pbar.update(len(chunk))

        if downloaded != expected_size:
            raise Exception(f"Download incomplete: got {downloaded} bytes, expected {expected_size}")

        # Calculate throughput
        throughput_mbps = (expected_mb * 8) / self.current_measurement['duration_seconds']

        return {
            'bytes_downloaded': downloaded,
            'throughput_mbps': throughput_mbps
        }

    def stream_file(self, file_id: int, range_header: Optional[str] = None) -> Dict[str, Any]:
        """Stream file and measure performance"""
        url = f"{self.server_url}/api/files/{file_id}/stream"
        headers = {}
        if range_header:
            headers['Range'] = range_header
            operation_type = f"stream_range_{range_header}"
        else:
            operation_type = "stream_full"

        # Get expected content length
        if range_header:
            # For range requests, we need to make a HEAD request first
            head_response = self.session.head(url, headers={'Range': range_header})
            if head_response.status_code != 206:
                raise Exception(f"Range request failed: HTTP {head_response.status_code}")
            expected_size = int(head_response.headers.get('Content-Length', 0))
        else:
            # For full stream, get from file info
            info_response = self.session.get(f"{self.server_url}/api/files/{file_id}")
            file_info = info_response.json()
            expected_size = file_info['size']

        expected_mb = expected_size / (1024 * 1024)

        self.log(f"Streaming {expected_mb:.1f} MB ({operation_type})...")

        response = self.session.get(url, headers=headers, stream=True)
        if response.status_code not in [200, 206]:
            raise Exception(f"Stream failed: HTTP {response.status_code}")

        # Stream with progress
        downloaded = 0
        with tqdm(total=expected_size, unit='B', unit_scale=True, desc=f"Streaming ({operation_type})") as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    pbar.update(len(chunk))

        throughput_mbps = (expected_mb * 8) / self.current_measurement['duration_seconds']

        return {
            'bytes_streamed': downloaded,
            'throughput_mbps': throughput_mbps,
            'status_code': response.status_code,
            'content_range': response.headers.get('Content-Range')
        }

    def transcode_file(self, file_id: int, qualities: list = None) -> Dict[str, Any]:
        """Trigger transcoding and measure performance"""
        if qualities is None:
            qualities = [480, 720]

        url = f"{self.server_url}/api/transcode"
        payload = {
            'file_id': file_id,
            'qualities': qualities
        }

        self.log(f"Triggering transcoding to {qualities}...")

        response = self.session.post(url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Transcode trigger failed: HTTP {response.status_code} - {response.text}")

        result = response.json()
        job_ids = [job['job_id'] for job in result.get('jobs', [])]

        self.log(f"Created {len(job_ids)} transcoding jobs: {job_ids}")

        return {
            'job_ids': job_ids,
            'qualities': qualities,
            'response': result
        }

    def wait_for_transcode_completion(self, job_ids: list, timeout_seconds: int = 3600) -> Dict[str, Any]:
        """Wait for transcoding jobs to complete and measure performance"""
        start_time = time.time()
        completed_jobs = {}
        failed_jobs = {}

        self.log(f"Waiting for {len(job_ids)} jobs to complete...")

        with tqdm(total=len(job_ids), desc="Transcoding") as pbar:
            while len(completed_jobs) + len(failed_jobs) < len(job_ids):
                if time.time() - start_time > timeout_seconds:
                    raise Exception(f"Transcode timeout after {timeout_seconds} seconds")

                for job_id in job_ids:
                    if job_id in completed_jobs or job_id in failed_jobs:
                        continue

                    try:
                        response = self.session.get(f"{self.server_url}/api/transcode/job/{job_id}")
                        if response.status_code != 200:
                            continue

                        job_data = response.json()
                        status = job_data['status']

                        if status == 'completed':
                            completed_jobs[job_id] = job_data
                            pbar.update(1)
                        elif status == 'failed':
                            failed_jobs[job_id] = job_data
                            pbar.update(1)

                    except Exception as e:
                        self.log(f"Error checking job {job_id}: {e}")
                        continue

                time.sleep(2)  # Poll every 2 seconds

        total_duration = time.time() - start_time

        # Calculate performance metrics
        if completed_jobs:
            avg_completion_time = sum(
                (datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00')) -
                 datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))).total_seconds()
                for job in completed_jobs.values()
            ) / len(completed_jobs)

            total_output_size = sum(job.get('output_size', 0) for job in completed_jobs.values())
        else:
            avg_completion_time = 0
            total_output_size = 0

        return {
            'total_duration_seconds': total_duration,
            'completed_jobs': len(completed_jobs),
            'failed_jobs': len(failed_jobs),
            'avg_completion_time_seconds': avg_completion_time,
            'total_output_size_mb': total_output_size / (1024 * 1024) if total_output_size else 0,
            'jobs_details': {**completed_jobs, **failed_jobs}
        }

    def run_full_benchmark(self, file_path: str) -> Dict[str, Any]:
        """Run complete benchmark suite"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'server_url': self.server_url,
            'file_info': self.get_file_info(file_path),
            'measurements': []
        }

        try:
            # 1. Upload
            upload_result = self.measure_operation('upload', self.upload_file, file_path)
            results['measurements'].append(upload_result)
            file_id = upload_result['result']['file_id'] if upload_result['success'] else None

            if not upload_result['success']:
                return results

            # 2. Download
            download_result = self.measure_operation('download', self.download_file, file_id)
            results['measurements'].append(download_result)

            # 3. Stream full file
            stream_full_result = self.measure_operation('stream_full', self.stream_file, file_id)
            results['measurements'].append(stream_full_result)

            # 4. Stream partial range (first 50MB)
            stream_range_result = self.measure_operation(
                'stream_range', self.stream_file, file_id, "bytes=0-52428800"
            )
            results['measurements'].append(stream_range_result)

            # 5. Transcode
            transcode_trigger_result = self.measure_operation(
                'transcode_trigger', self.transcode_file, file_id, [480, 720]
            )
            results['measurements'].append(transcode_trigger_result)

            if transcode_trigger_result['success']:
                job_ids = transcode_trigger_result['result']['job_ids']
                transcode_wait_result = self.measure_operation(
                    'transcode_wait', self.wait_for_transcode_completion, job_ids
                )
                results['measurements'].append(transcode_wait_result)

        except Exception as e:
            self.log(f"Benchmark failed: {e}")
            results['error'] = str(e)

        return results

    def print_report(self, results: Dict[str, Any]):
        """Print formatted benchmark report"""
        print("\n" + "="*80)
        print("🚀 NEBULA PERFORMANCE BENCHMARK REPORT")
        print("="*80)

        file_info = results['file_info']
        print("\n📁 Test File:")
        print(f"   Path: {file_info['path']}")
        print(f"   Size: {file_info['size_mb']:.1f} MB ({file_info['size_bytes']:,} bytes)")

        print(f"\n🔗 Server: {results['server_url']}")
        print(f"📅 Timestamp: {results['timestamp']}")

        if 'error' in results:
            print(f"\n❌ Benchmark failed: {results['error']}")
            return

        # Print measurements
        print("\n📊 PERFORMANCE RESULTS:")
        print("-" * 60)

        for measurement in results['measurements']:
            op = measurement['operation']
            duration = measurement['duration_seconds']
            success = measurement['success']

            status_icon = "✅" if success else "❌"
            print(f"\n{status_icon} {op.replace('_', ' ').title()}")

            if success:
                result = measurement['result']

                if 'throughput_mbps' in result:
                    print(".1f")
                if 'bytes_downloaded' in result:
                    print(f"   Data: {result['bytes_downloaded'] / (1024*1024):.1f} MB")
                if 'bytes_streamed' in result:
                    print(f"   Data: {result['bytes_streamed'] / (1024*1024):.1f} MB")
                if 'job_ids' in result:
                    print(f"   Jobs: {len(result['job_ids'])} created")
                if 'completed_jobs' in result:
                    print(f"   Jobs: {result['completed_jobs']} completed, {result['failed_jobs']} failed")
                    if result['avg_completion_time_seconds'] > 0:
                        print(".1f")
                    if result['total_output_size_mb'] > 0:
                        print(".1f")
            else:
                print(f"   Error: {measurement.get('error', 'Unknown')}")

            print(".2f")
        # Summary insights
        print("\n💡 INSIGHTS:")
        print("-" * 60)

        measurements = results['measurements']

        # Upload vs Download comparison
        upload = next((m for m in measurements if m['operation'] == 'upload'), None)
        download = next((m for m in measurements if m['operation'] == 'download'), None)

        if upload and download and upload['success'] and download['success']:
            upload_speed = upload['result']['throughput_mbps']
            download_speed = download['result']['throughput_mbps']
            ratio = download_speed / upload_speed if upload_speed > 0 else 0

            print(f"   Upload: {upload_speed:.1f} Mbps | Download: {download_speed:.1f} Mbps | Ratio: {ratio:.2f}")
            if ratio < 0.8:
                print("   → Upload >> Download: Possible read bottleneck (MinIO/disk)")
            elif ratio > 1.2:
                print("   → Download >> Upload: Possible write bottleneck")

        # Stream vs Download comparison
        stream_full = next((m for m in measurements if m['operation'] == 'stream_full'), None)
        if download and stream_full and download['success'] and stream_full['success']:
            download_speed = download['result']['throughput_mbps']
            stream_speed = stream_full['result']['throughput_mbps']
            ratio = stream_speed / download_speed if download_speed > 0 else 0

            print(f"   Download: {download_speed:.1f} Mbps | Stream: {stream_speed:.1f} Mbps | Ratio: {ratio:.2f}")
            if ratio < 0.9:
                print("   → Streaming slower: Extra overhead in range handling")

        # Transcoding insights
        transcode_wait = next((m for m in measurements if m['operation'] == 'transcode_wait'), None)
        if transcode_wait and transcode_wait['success']:
            result = transcode_wait['result']
            if result['completed_jobs'] > 0:
                input_duration_hours = file_info['size_mb'] / (50 * 1024)  # Rough estimate: 50MB/min video
                processing_time_hours = result['avg_completion_time_seconds'] / 3600
                speedup = input_duration_hours / processing_time_hours if processing_time_hours > 0 else 0

                print(f"   Processing time: {processing_time_hours:.1f} hours")
                print(f"   Speedup: {speedup:.1f}x real-time")

        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Nebula Cloud performance")
    parser.add_argument("file_path", help="Path to video file to benchmark")
    parser.add_argument("--server", default="http://localhost:8000",
                       help="Nebula server URL (default: http://localhost:8000)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--output", "-o",
                       help="Save results to JSON file")

    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"❌ File not found: {args.file_path}")
        sys.exit(1)

    # Check if required packages are available
    try:
        import requests
        import tqdm
    except ImportError as e:
        print(f"❌ Missing required packages: {e}")
        print("Install with: pip install requests tqdm")
        sys.exit(1)

    print("🚀 Starting Nebula Performance Benchmark...")
    print(f"📁 File: {args.file_path}")
    print(f"🔗 Server: {args.server}")
    print()

    benchmark = NebulaBenchmark(args.server, args.verbose)
    results = benchmark.run_full_benchmark(args.file_path)
    benchmark.print_report(results)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()
