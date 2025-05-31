import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { useDropzone } from 'react-dropzone'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

function App() {
  const [videoFile, setVideoFile] = useState(null)
  const [imageFile, setImageFile] = useState(null)
  const [videoId, setVideoId] = useState(null)
  const [imageId, setImageId] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [ws, setWs] = useState(null)
  const intervalRef = useRef(null)

  // WebSocket接続
  useEffect(() => {
    if (jobId) {
      const websocket = new WebSocket(`${WS_URL}/ws`)
      
      websocket.onopen = () => {
        console.log('WebSocket接続完了')
      }
      
      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        console.log('WebSocketメッセージ受信:', data)
        if (data.job_id === jobId || data.job_id === taskId) {
          setJobStatus(data)
        }
      }
      
      websocket.onerror = (error) => {
        console.error('WebSocketエラー:', error)
      }
      
      setWs(websocket)
      
      return () => {
        websocket.close()
      }
    }
  }, [jobId, taskId])

  // ポーリングでタスク状態を確認（WebSocketのバックアップ）
  useEffect(() => {
    if (taskId) {
      // 初回チェック
      checkTaskStatus()
      
      // 定期的にチェック
      intervalRef.current = setInterval(() => {
        checkTaskStatus()
      }, 2000) // 2秒ごと
      
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
        }
      }
    }
  }, [taskId])

  const checkTaskStatus = async () => {
    if (!taskId) return
    
    try {
      const response = await axios.get(`${API_URL}/api/job/${taskId}`)
      const data = response.data
      console.log('タスク状態:', data)
      
      setJobStatus(data)
      
      // 完了または失敗したらポーリング停止
      if (data.status === 'completed' || data.status === 'failed') {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    } catch (error) {
      console.error('タスク状態確認エラー:', error)
    }
  }

  const onDropVideo = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    setVideoFile(file)
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await axios.post(`${API_URL}/api/upload/video`, formData)
      setVideoId(response.data.file_id)
    } catch (error) {
      console.error('動画アップロードエラー:', error)
    }
  }

  const onDropImage = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    setImageFile(file)
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await axios.post(`${API_URL}/api/upload/image`, formData)
      setImageId(response.data.file_id)
    } catch (error) {
      console.error('画像アップロードエラー:', error)
    }
  }

  const startProcessing = async () => {
    if (!videoId || !imageId) {
      alert('動画と画像を両方アップロードしてください')
      return
    }
    
    try {
      const response = await axios.post(`${API_URL}/api/process`, {
        video_id: videoId,
        image_id: imageId
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      console.log('処理開始レスポンス:', response.data)
      
      // 新しいCelery版のレスポンスに対応
      if (response.data.task_id) {
        setTaskId(response.data.task_id)
        setJobId(response.data.job_id || response.data.task_id)
        // 初期状態を設定
        setJobStatus({
          job_id: response.data.job_id || response.data.task_id,
          status: response.data.status || 'queued',
          progress: 0,
          message: response.data.message || '処理待機中...'
        })
      } else {
        // 旧バージョンのレスポンス
        setJobId(response.data.job_id)
      }
    } catch (error) {
      console.error('処理開始エラー:', error)
      if (error.response && error.response.data) {
        console.error('エラー詳細:', error.response.data)
        alert(`エラー: ${JSON.stringify(error.response.data)}`)
      }
    }
  }

  const { getRootProps: getVideoRootProps, getInputProps: getVideoInputProps } = useDropzone({
    onDrop: onDropVideo,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.webm']
    },
    maxFiles: 1
  })

  const { getRootProps: getImageRootProps, getInputProps: getImageInputProps } = useDropzone({
    onDrop: onDropImage,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png']
    },
    maxFiles: 1
  })

  const getStatusText = (status) => {
    switch (status) {
      case 'pending':
      case 'queued':
        return '待機中'
      case 'processing':
      case 'PROGRESS':
        return '処理中'
      case 'completed':
      case 'SUCCESS':
        return '完了'
      case 'failed':
      case 'FAILURE':
        return '失敗'
      default:
        return status
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
      case 'SUCCESS':
        return 'text-green-600'
      case 'failed':
      case 'FAILURE':
        return 'text-red-600'
      case 'processing':
      case 'PROGRESS':
        return 'text-blue-600'
      default:
        return 'text-gray-600'
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-center mb-8">FaceFusion 顔交換アプリ</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div>
            <h2 className="text-xl font-semibold mb-4">動画をアップロード</h2>
            <div {...getVideoRootProps()} className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400">
              <input {...getVideoInputProps()} />
              {videoFile ? (
                <p className="text-green-600">✓ {videoFile.name}</p>
              ) : (
                <p>動画をドラッグ＆ドロップまたはクリックして選択</p>
              )}
            </div>
          </div>
          
          <div>
            <h2 className="text-xl font-semibold mb-4">顔画像をアップロード</h2>
            <div {...getImageRootProps()} className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400">
              <input {...getImageInputProps()} />
              {imageFile ? (
                <p className="text-green-600">✓ {imageFile.name}</p>
              ) : (
                <p>画像をドラッグ＆ドロップまたはクリックして選択</p>
              )}
            </div>
          </div>
        </div>
        
        <div className="text-center mb-8">
          <button
            onClick={startProcessing}
            disabled={!videoFile || !imageFile || jobId}
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded disabled:bg-gray-400"
          >
            処理開始
          </button>
        </div>
        
        {jobStatus && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">処理状況</h3>
            <div className="mb-4">
              <div className="flex justify-between mb-2">
                <span className={getStatusColor(jobStatus.status)}>
                  ステータス: {getStatusText(jobStatus.status)}
                </span>
                <span>{jobStatus.progress || 0}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-500" 
                  style={{ width: `${jobStatus.progress || 0}%` }}
                ></div>
              </div>
              {jobStatus.message && (
                <p className="text-sm text-gray-600 mt-2">{jobStatus.message}</p>
              )}
            </div>
            
            {(jobStatus.status === 'completed' || jobStatus.status === 'SUCCESS') && jobStatus.output_url && (
              <div className="text-center">
                <a 
                  href={`${API_URL}${jobStatus.output_url}`}
                  className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded inline-block"
                  download
                >
                  結果をダウンロード
                </a>
              </div>
            )}
            
            {jobStatus.error && (
              <div className="text-red-600 mt-4">
                エラー: {jobStatus.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default App