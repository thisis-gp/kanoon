import { useEffect, useRef } from "react";
import gsap from "gsap";
import Peep, {
  normalWalk,
  removeRandomFromArray,
  getRandomFromArray,
  resetPeep,
  removeItemFromArray,
} from "../lib/peep";

const PeopleCanvas = () => {
  const canvasRef = useRef(null);
  const allPeeps = useRef([]);
  const availablePeeps = useRef([]);
  const crowd = useRef([]);
  const stage = useRef({ width: 0, height: 0 });

  useEffect(() => {
    const image = new Image();
    image.src = "/assets/open-peeps-sheet.png"; // Make sure the image is in public folder
    image.onload = () => init(image);

    return () => {
      window.removeEventListener("resize", resize);
      gsap.ticker.remove(render);
    };
  }, []);

  const init = (img) => {
    createPeeps(img);
    resize();
    window.addEventListener("resize", resize);
    gsap.ticker.add(render);
  };

  const createPeeps = (img) => {
    const rows = 15,
      cols = 7;
    const { naturalWidth: width, naturalHeight: height } = img;
    const rectWidth = width / rows,
      rectHeight = height / cols;

    const peeps = [];
    for (let i = 0; i < rows * cols; i++) {
      peeps.push(
        new Peep({
          image: img,
          rect: [
            (i % rows) * rectWidth,
            Math.floor(i / rows) * rectHeight,
            rectWidth,
            rectHeight,
          ],
        })
      );
    }
    allPeeps.current = peeps;
    availablePeeps.current = [...peeps];
  };

  const resize = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    stage.current = {
      width: canvas.clientWidth,
      height: canvas.clientHeight,
    };

    canvas.width = stage.current.width * window.devicePixelRatio;
    canvas.height = stage.current.height * window.devicePixelRatio;

    // Clear existing crowd
    crowd.current.forEach((peep) => peep.walk?.kill());
    crowd.current = [];
    availablePeeps.current = [...allPeeps.current];
    initCrowd();
  };

  const initCrowd = () => {
    while (availablePeeps.current.length > 0) {
      addPeepToCrowd();
    }
  };

  const addPeepToCrowd = () => {
    const peep = removeRandomFromArray(availablePeeps.current);
    const walk = getRandomFromArray([normalWalk])({
      peep,
      props: resetPeep({ peep, stage: stage.current }),
    }).eventCallback("onComplete", () => {
      removePeepFromCrowd(peep);
      addPeepToCrowd();
    });

    peep.walk = walk;
    crowd.current.push(peep);
    crowd.current.sort((a, b) => a.anchorY - b.anchorY);
  };

  const removePeepFromCrowd = (peep) => {
    removeItemFromArray(crowd.current, peep);
    availablePeeps.current.push(peep);
  };

  const render = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    crowd.current.forEach((peep) => peep.render(ctx));
    ctx.restore();
  };

  return (
    <canvas
      ref={canvasRef}
      className="fixed top-0 left-0 w-full h-full z-0 pointer-events-none"
    />
  );
};

export default PeopleCanvas;